import * as path from 'path';
import { CfnOutput, Duration, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import * as apigwi from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as apigwa from 'aws-cdk-lib/aws-apigatewayv2-authorizers';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as cw from 'aws-cdk-lib/aws-cloudwatch';
import * as ddb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { StageProps, nag } from './common';

const ROOT = path.resolve(__dirname, '../../..');

export interface ClaimsProps extends StackProps, StageProps {
  webOrigins: string[];
  /** ChainTrack stage whose ledger/Cognito this reads. Empty = demo fixture, dev auth. */
  ledgerStage: string;
  webUrl: string;
}

/** MRUDDUNI.md 3.11: claims table, claim evidence bucket, ClaimGuard + Review API Lambda, HTTP API, SSM exports. */
export class ClaimsStack extends Stack {
  constructor(scope: Construct, id: string, props: ClaimsProps) {
    super(scope, id, props);
    const { stage, ledgerStage } = props;
    const prod = stage === 'prod';
    const removal = prod ? RemovalPolicy.RETAIN : RemovalPolicy.DESTROY;
    const live = ledgerStage !== '';

    const dataKey = new kms.Key(this, 'DataKey', { alias: `alias/oae-${stage}-claims`, enableKeyRotation: true, removalPolicy: removal });

    const table = new ddb.Table(this, 'Claims', {
      tableName: `oae-${stage}-claims`,
      partitionKey: { name: 'PK', type: ddb.AttributeType.STRING },
      sortKey: { name: 'SK', type: ddb.AttributeType.STRING },
      billingMode: ddb.BillingMode.PAY_PER_REQUEST,
      encryption: ddb.TableEncryption.CUSTOMER_MANAGED, encryptionKey: dataKey,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      deletionProtection: prod, removalPolicy: removal,
    });
    table.addGlobalSecondaryIndex({
      indexName: 'GSI1',
      partitionKey: { name: 'GSI1PK', type: ddb.AttributeType.STRING },
      sortKey: { name: 'GSI1SK', type: ddb.AttributeType.STRING },
    });
    table.addGlobalSecondaryIndex({
      indexName: 'GSI3',
      partitionKey: { name: 'GSI3PK', type: ddb.AttributeType.STRING },
      sortKey: { name: 'GSI3SK', type: ddb.AttributeType.STRING },
    });

    const accessLogs = new s3.Bucket(this, 'AccessLogs', {
      bucketName: `oae-${stage}-claims-access-logs-${this.account}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL, enforceSSL: true,
      objectOwnership: s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
      lifecycleRules: [{ expiration: Duration.days(30) }], removalPolicy: removal, autoDeleteObjects: !prod,
    });
    nag(accessLogs, 'AwsSolutions-S1', 'This is the access-log target bucket; logging it to itself would loop.');

    const evidenceBucket = new s3.Bucket(this, 'ClaimEvidence', {
      bucketName: `oae-${stage}-claim-evidence-${this.account}`,
      encryption: s3.BucketEncryption.KMS, encryptionKey: dataKey, bucketKeyEnabled: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL, enforceSSL: true,
      serverAccessLogsBucket: accessLogs, serverAccessLogsPrefix: 'claim-evidence/',
      eventBridgeEnabled: true,
      cors: [{ allowedMethods: [s3.HttpMethods.PUT, s3.HttpMethods.GET], allowedOrigins: props.webOrigins, allowedHeaders: ['*'], maxAge: 3000 }],
      removalPolicy: removal, autoDeleteObjects: !prod,
    });

    // --- Lambda ---------------------------------------------------------------------------------
    const powertools = lambda.LayerVersion.fromLayerVersionArn(this, 'Powertools',
      ssm.StringParameter.valueForStringParameter(this, '/aws/service/powertools/python/arm64/python3.12/latest'));
    const deps = new lambda.LayerVersion(this, 'Deps', {
      code: lambda.Code.fromAsset(path.join(ROOT, '.build/claimguard/deps')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12], compatibleArchitectures: [lambda.Architecture.ARM_64],
      description: 'pyyaml (arm64)',
    });
    const logGroup = new logs.LogGroup(this, 'ReviewApiLogs', {
      logGroupName: `/aws/lambda/oae-${stage}-review-api`, retention: logs.RetentionDays.ONE_MONTH, removalPolicy: RemovalPolicy.DESTROY,
    });
    const origin = props.webOrigins[0] ?? '*';
    const ledgerTable = live ? ssm.StringParameter.valueForStringParameter(this, `/openaeye/${ledgerStage}/ledger/table-name`) : '';
    const fn = new lambda.Function(this, 'ReviewApi', {
      functionName: `oae-${stage}-review-api`,
      runtime: lambda.Runtime.PYTHON_3_12, architecture: lambda.Architecture.ARM_64,
      handler: 'review.handler.handler',
      code: lambda.Code.fromAsset(path.join(ROOT, '.build/claimguard/app')),
      layers: [powertools, deps],
      timeout: Duration.seconds(29), memorySize: 512, tracing: lambda.Tracing.ACTIVE, logGroup,
      environment: {
        STAGE: stage,
        AUTH_MODE: live ? 'jwt' : 'dev',
        CLAIMS_TABLE: table.tableName,
        ...(live ? { LEDGER_TABLE: ledgerTable } : { LEDGER_FIXTURE: '/var/task/data/fixtures/ledger_events.json' }),
        SOURCES_PATH: '/var/task/data/sources.yaml',
        CLAIM_EVIDENCE_BUCKET: evidenceBucket.bucketName,
        ALLOW_ORIGIN: origin,
        POWERTOOLS_SERVICE_NAME: 'claimguard',
      },
    });
    nag(fn, 'AwsSolutions::AwsSolutions-L1', 'CONTRACT §2 fixes Python 3.12 for both apps.');
    table.grantReadWriteData(fn);
    dataKey.grantEncryptDecrypt(fn);
    evidenceBucket.grantReadWrite(fn);
    if (live) {
      // Read-only on the ChainTrack ledger (CONTRACT §6: Mrudduni reads only). Its key policy lets the account's IAM principals use it.
      const ledgerArn = ssm.StringParameter.valueForStringParameter(this, `/openaeye/${ledgerStage}/ledger/table-arn`);
      fn.addToRolePolicy(new iam.PolicyStatement({
        actions: ['dynamodb:GetItem', 'dynamodb:Query', 'dynamodb:Scan', 'dynamodb:BatchGetItem'],
        resources: [ledgerArn],
      }));
      fn.addToRolePolicy(new iam.PolicyStatement({
        actions: ['kms:Decrypt', 'kms:DescribeKey'], resources: ['*'],
        conditions: { StringEquals: { 'kms:ViaService': `dynamodb.${this.region}.amazonaws.com` } },
      }));
    }
    new cw.Alarm(this, 'ReviewApiErrors', {
      alarmName: `oae-${stage}-review-api-errors`, metric: fn.metricErrors({ period: Duration.minutes(5), statistic: 'Sum' }),
      threshold: 3, evaluationPeriods: 1, treatMissingData: cw.TreatMissingData.NOT_BREACHING,
      comparisonOperator: cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
    });

    // --- HTTP API ---------------------------------------------------------------------------------
    const apiLogs = new logs.LogGroup(this, 'ApiAccessLogs', {
      logGroupName: `/aws/apigateway/oae-${stage}-review`, retention: logs.RetentionDays.ONE_MONTH, removalPolicy: RemovalPolicy.DESTROY,
    });
    const http = new apigw.HttpApi(this, 'HttpApi', {
      apiName: `oae-${stage}-review`,
      corsPreflight: {
        allowOrigins: props.webOrigins,
        allowMethods: [apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST, apigw.CorsHttpMethod.OPTIONS],
        allowHeaders: ['authorization', 'content-type', 'x-dev-party', 'x-dev-role'],
        maxAge: Duration.hours(1),
      },
    });
    const cfnStage = http.defaultStage!.node.defaultChild as apigw.CfnStage;
    cfnStage.defaultRouteSettings = { throttlingRateLimit: 20, throttlingBurstLimit: 40 };
    cfnStage.accessLogSettings = {
      destinationArn: apiLogs.logGroupArn,
      format: JSON.stringify({ requestId: '$context.requestId', ip: '$context.identity.sourceIp', route: '$context.routeKey',
        status: '$context.status', latency: '$context.responseLatency', error: '$context.error.message' }),
    };
    const integ = new apigwi.HttpLambdaIntegration('ReviewInteg', fn);
    let authorizer: apigwa.HttpUserPoolAuthorizer | undefined;
    if (live) {
      const poolId = ssm.StringParameter.valueForStringParameter(this, `/openaeye/${ledgerStage}/auth/user-pool-id`);
      const clientId = ssm.StringParameter.valueForStringParameter(this, `/openaeye/${ledgerStage}/auth/user-pool-client-id-review`);
      authorizer = new apigwa.HttpUserPoolAuthorizer('Cognito',
        cognito.UserPool.fromUserPoolId(this, 'Pool', poolId),
        { userPoolClients: [cognito.UserPoolClient.fromUserPoolClientId(this, 'ReviewClient', clientId)], identitySource: ['$request.header.Authorization'] });
    }
    const secured: [string, apigw.HttpMethod][] = [
      ['/claims', apigw.HttpMethod.GET], ['/claims', apigw.HttpMethod.POST],
      ['/claims/{claim_id}', apigw.HttpMethod.GET], ['/claims/{claim_id}/check', apigw.HttpMethod.POST],
      ['/claims/{claim_id}/runs/{run_id}', apigw.HttpMethod.GET], ['/claims/{claim_id}/reviews', apigw.HttpMethod.POST],
      ['/claim-evidence/presign', apigw.HttpMethod.POST],
    ];
    const open: [string, apigw.HttpMethod][] = [['/impact', apigw.HttpMethod.GET], ['/sources/{source_id}', apigw.HttpMethod.GET]];
    for (const [p, m] of secured) {
      for (const r of http.addRoutes({ path: p, methods: [m], integration: integ, authorizer })) {
        if (!live) nag(r.node.defaultChild!, 'AwsSolutions::AwsSolutions-APIG4',
          'Dev stage serves synthetic demo data only and trusts X-Dev-* headers (AUTH_MODE=dev); deploying with -c ledgerStage attaches the Cognito authorizer.');
      }
    }
    for (const [p, m] of open) {
      for (const r of http.addRoutes({ path: p, methods: [m], integration: integ })) {
        nag(r.node.defaultChild!, 'AwsSolutions::AwsSolutions-APIG4', 'Public by design: impact numbers and their sources carry no personal data.');
      }
    }

    // --- SSM exports (CONTRACT §2) ----------------------------------------------------------------
    const p = (id: string, name: string, value: string) =>
      new ssm.StringParameter(this, id, { parameterName: `/openaeye/${stage}/${name}`, stringValue: value });
    p('PClaimsTable', 'claims/table-name', table.tableName);
    p('PClaimsTableArn', 'claims/table-arn', table.tableArn);
    p('PReviewApi', 'review/api-url', http.apiEndpoint);
    new CfnOutput(this, 'ReviewApiUrl', { value: http.apiEndpoint });
    new CfnOutput(this, 'ClaimsTable', { value: table.tableName });

    const iam5: [string, string][] = [
      ['Action::kms:GenerateDataKey*', 'CDK grantEncryptDecrypt on the stage claims key only.'],
      ['Action::kms:ReEncrypt*', 'CDK grantEncryptDecrypt on the stage claims key only.'],
      ['Action::s3:Abort*', 'Multipart abort on the stage claim-evidence bucket only.'],
      ['Action::s3:DeleteObject*', 'Review API may replace claim evidence it wrote, stage bucket only.'],
      ['Action::s3:GetBucket*', 'Scoped to the stage claim-evidence bucket.'],
      ['Action::s3:GetObject*', 'Scoped to the stage claim-evidence bucket.'],
      ['Action::s3:List*', 'Scoped to the stage claim-evidence bucket.'],
      ['Resource::*', 'X-Ray PutTraceSegments does not support resource-level permissions; kms:Decrypt on the ledger is constrained to DynamoDB via kms:ViaService.'],
      [`Resource::<${this.getLogicalId(table.node.defaultChild as ddb.CfnTable)}.Arn>/index/*`, 'Indexes (GSI1, GSI3) of the stage claims table.'],
      [`Resource::<${this.getLogicalId(evidenceBucket.node.defaultChild as s3.CfnBucket)}.Arn>/*`, 'Objects of the stage claim-evidence bucket.'],
    ];
    for (const [k, why] of iam5) nag(this, `AwsSolutions::AwsSolutions-IAM5[${k}]`, why);
    nag(this, 'AwsSolutions::AwsSolutions-IAM4[Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole]',
      'AWSLambdaBasicExecutionRole is the standard managed policy for CloudWatch Logs (also used by the S3 auto-delete custom resource).');
  }
}
