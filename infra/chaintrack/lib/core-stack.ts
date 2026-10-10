import * as fs from 'fs';
import * as path from 'path';
import { Duration, RemovalPolicy, Stack, StackProps, CfnOutput } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as ddb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as avp from 'aws-cdk-lib/aws-verifiedpermissions';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { nag, StageProps } from './common';
import { loadCedarPolicies } from './cedar';

export interface CoreStackProps extends StackProps, StageProps {
  webOrigins: string[];
  digestRetentionDays: number;
}

/** SHAURYA.md 3.1: keys, ledger table, buckets, user pool, policy store, SSM exports. */
export class CoreStack extends Stack {
  readonly dataKey: kms.Key;
  readonly signingKey: kms.Key;
  readonly phoneHmacKey: kms.Key;
  readonly table: ddb.Table;
  readonly evidenceBucket: s3.Bucket;
  readonly digestBucket: s3.Bucket;
  readonly userPool: cognito.UserPool;
  readonly captureClient: cognito.UserPoolClient;
  readonly policyStoreId: string;

  constructor(scope: Construct, id: string, props: CoreStackProps) {
    super(scope, id, props);
    const { stage } = props;
    const prod = stage === 'prod';
    const removal = prod ? RemovalPolicy.RETAIN : RemovalPolicy.DESTROY;
    const param = (name: string, value: string) =>
      new ssm.StringParameter(this, `P-${name.replace(/[^A-Za-z0-9]/g, '-')}`, {
        parameterName: `/openaeye/${stage}/${name}`, stringValue: value,
      });

    // --- KMS ---------------------------------------------------------------
    this.dataKey = new kms.Key(this, 'DataKey', {
      alias: `alias/oae-${stage}-data`, enableKeyRotation: true, removalPolicy: removal,
      description: 'OpenAEye: S3 and DynamoDB encryption',
    });
    this.signingKey = new kms.Key(this, 'LedgerSigningKey', {
      alias: `alias/oae-${stage}-ledger-signing`,
      keySpec: kms.KeySpec.ECC_NIST_P256, keyUsage: kms.KeyUsage.SIGN_VERIFY,
      removalPolicy: RemovalPolicy.RETAIN, // losing it would make every past signature unverifiable
      description: 'OpenAEye: ECDSA P-256 signatures over ledger event hashes',
    });
    this.phoneHmacKey = new kms.Key(this, 'PhoneHmacKey', {
      alias: `alias/oae-${stage}-phone-hmac`,
      keySpec: kms.KeySpec.HMAC_256, keyUsage: kms.KeyUsage.GENERATE_VERIFY_MAC,
      removalPolicy: removal,
      description: 'OpenAEye: HMAC of phone numbers; plain numbers are never stored',
    });

    // --- Ledger table (CONTRACT §6) ------------------------------------------
    this.table = new ddb.Table(this, 'Ledger', {
      tableName: `oae-${stage}-ledger`,
      partitionKey: { name: 'PK', type: ddb.AttributeType.STRING },
      sortKey: { name: 'SK', type: ddb.AttributeType.STRING },
      billingMode: ddb.BillingMode.PAY_PER_REQUEST,
      encryption: ddb.TableEncryption.CUSTOMER_MANAGED, encryptionKey: this.dataKey,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      deletionProtection: prod,
      timeToLiveAttribute: 'expires_at',
      removalPolicy: removal,
    });
    this.table.addGlobalSecondaryIndex({
      indexName: 'GSI2',
      partitionKey: { name: 'GSI2PK', type: ddb.AttributeType.STRING },
      sortKey: { name: 'GSI2SK', type: ddb.AttributeType.STRING },
    });

    // --- Buckets -------------------------------------------------------------
    const logs = new s3.Bucket(this, 'AccessLogs', {
      bucketName: `oae-${stage}-access-logs-${this.account}`,
      encryption: s3.BucketEncryption.S3_MANAGED, // log delivery cannot write to SSE-KMS buckets
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL, enforceSSL: true,
      objectOwnership: s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
      lifecycleRules: [{ expiration: Duration.days(30) }],
      removalPolicy: removal,
    });
    nag(logs, 'AwsSolutions-S1', 'This is the access-log target bucket; logging it to itself would loop.');

    this.evidenceBucket = new s3.Bucket(this, 'CaptureEvidence', {
      bucketName: `oae-${stage}-capture-evidence-${this.account}`,
      encryption: s3.BucketEncryption.KMS, encryptionKey: this.dataKey, bucketKeyEnabled: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL, enforceSSL: true,
      serverAccessLogsBucket: logs, serverAccessLogsPrefix: 'capture-evidence/',
      eventBridgeEnabled: true, // CONTRACT/SHAURYA §7 step 6: ObjectCreated -> evidence processor
      lifecycleRules: [{ id: 'raw-voice-24h', prefix: 'audio/', expiration: Duration.days(1) }],
      cors: [{
        allowedMethods: [s3.HttpMethods.PUT, s3.HttpMethods.GET],
        allowedOrigins: props.webOrigins, allowedHeaders: ['*'], maxAge: 3000,
      }],
      removalPolicy: removal,
    });

    this.digestBucket = new s3.Bucket(this, 'LedgerDigests', {
      bucketName: `oae-${stage}-ledger-digests-${this.account}`,
      objectLockEnabled: true,
      objectLockDefaultRetention: s3.ObjectLockRetention.compliance(Duration.days(props.digestRetentionDays)),
      versioned: true,
      encryption: s3.BucketEncryption.KMS, encryptionKey: this.dataKey, bucketKeyEnabled: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL, enforceSSL: true,
      serverAccessLogsBucket: logs, serverAccessLogsPrefix: 'ledger-digests/',
      removalPolicy: RemovalPolicy.RETAIN, // compliance-locked objects cannot be deleted anyway
    });

    nag(this, 'AwsSolutions::AwsSolutions-IAM4[Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole]',
      'CDK-internal BucketNotificationsHandler (enables EventBridge on the evidence bucket); only needs CloudWatch Logs.');

    // --- Cognito (business users only; handlers never get accounts) -----------
    this.userPool = new cognito.UserPool(this, 'Users', {
      userPoolName: `oae-${stage}-users`,
      selfSignUpEnabled: false,
      signInAliases: { username: true, email: true },
      customAttributes: { party_id: new cognito.StringAttribute({ mutable: false, minLen: 5, maxLen: 12 }) },
      passwordPolicy: { minLength: 12, requireDigits: true, requireLowercase: true, requireUppercase: true, requireSymbols: true },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      mfa: cognito.Mfa.OPTIONAL, mfaSecondFactor: { sms: false, otp: true },
      removalPolicy: removal,
    });
    nag(this.userPool, 'AwsSolutions::AwsSolutions-COG2', 'MFA is optional (TOTP) for demo accounts; SMS MFA is impossible in India without DLT registration. Revisit for a pilot.');
    nag(this.userPool, 'AwsSolutions::AwsSolutions-COG8', 'Cognito Plus tier (threat protection) has a monthly cost; not approved for the hackathon. Revisit for a pilot.');
    for (const g of ['COLLECTOR', 'AGGREGATOR', 'RECYCLER', 'AUDITOR', 'PRODUCER']) {
      new cognito.CfnUserPoolGroup(this, `Group${g}`, { userPoolId: this.userPool.userPoolId, groupName: g });
    }
    const clientProps = (name: string): cognito.UserPoolClientOptions => ({
      userPoolClientName: name, generateSecret: false, preventUserExistenceErrors: true,
      authFlows: { userSrp: true },
      accessTokenValidity: Duration.hours(1), idTokenValidity: Duration.hours(1), refreshTokenValidity: Duration.days(30),
    });
    this.captureClient = this.userPool.addClient('CaptureClient', clientProps(`oae-${stage}-capture`));
    const reviewClient = this.userPool.addClient('ReviewClient', clientProps(`oae-${stage}-review`));

    // --- Verified Permissions (Cedar from policies/) -----------------------------
    const policyDir = path.join(__dirname, '..', '..', '..', 'policies');
    const store = new avp.CfnPolicyStore(this, 'PolicyStore', {
      description: `OpenAEye ${stage} field-level access control`,
      validationSettings: { mode: 'STRICT' },
      schema: { cedarJson: fs.readFileSync(path.join(policyDir, 'schema.cedarschema.json'), 'utf8') },
    });
    for (const p of loadCedarPolicies(policyDir)) {
      new avp.CfnPolicy(this, `Policy-${p.id}`, {
        policyStoreId: store.attrPolicyStoreId,
        definition: { static: { description: p.id, statement: p.statement } },
      });
    }
    this.policyStoreId = store.attrPolicyStoreId;

    // --- SSM exports (CONTRACT §2) --------------------------------------------------
    param('ledger/table-name', this.table.tableName);
    param('ledger/table-arn', this.table.tableArn);
    param('ledger/signing-key-arn', this.signingKey.keyArn);
    param('capture/evidence-bucket', this.evidenceBucket.bucketName);
    param('auth/user-pool-id', this.userPool.userPoolId);
    param('auth/user-pool-client-id-review', reviewClient.userPoolClientId);
    param('authz/policy-store-id', store.attrPolicyStoreId);
    // Shaurya-internal (not in the contract)
    param('ledger/digest-bucket', this.digestBucket.bucketName);
    param('ledger/phone-hmac-key-arn', this.phoneHmacKey.keyArn);
    param('auth/user-pool-client-id-capture', this.captureClient.userPoolClientId);

    new CfnOutput(this, 'TableName', { value: this.table.tableName });
    new CfnOutput(this, 'UserPoolId', { value: this.userPool.userPoolId });
    new CfnOutput(this, 'PolicyStoreId', { value: store.attrPolicyStoreId });
  }
}
