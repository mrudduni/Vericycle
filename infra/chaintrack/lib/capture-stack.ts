import * as path from 'path';
import { CfnOutput, Duration, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ddb from 'aws-cdk-lib/aws-dynamodb';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as scheduler from 'aws-cdk-lib/aws-scheduler';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subs from 'aws-cdk-lib/aws-sns-subscriptions';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import * as apigwi from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as apigwa from 'aws-cdk-lib/aws-apigatewayv2-authorizers';
import { CoreStack } from './core-stack';
import { nag, StageProps } from './common';

export interface CaptureStackProps extends StackProps, StageProps {
  core: CoreStack;
  webOrigins: string[];
  webUrl: string;
  modelId: string;          // Bedrock model or inference profile ID; "offline" = deterministic reader
  bedrockRegion: string;
  waNumber: string;         // digits only, or "" until the WhatsApp number is linked
  waPhoneNumberId: string;  // EUMS phone-number-id ARN; "" = WhatsApp resources not deployed
}

const ROOT = path.join(__dirname, '..', '..', '..');

export class CaptureStack extends Stack {
  readonly apiUrl: string;

  constructor(scope: Construct, id: string, props: CaptureStackProps) {
    super(scope, id, props);
    const { stage, core } = props;

    const modelParam = new ssm.StringParameter(this, 'ModelId', {
      parameterName: `/openaeye/${stage}/extract/model-id`, stringValue: props.modelId,
      description: 'Bedrock model or inference profile used for handover extraction',
    });

    const idemTable = new ddb.Table(this, 'Idempotency', {
      tableName: `oae-${stage}-idempotency`,
      partitionKey: { name: 'id', type: ddb.AttributeType.STRING },
      billingMode: ddb.BillingMode.PAY_PER_REQUEST,
      encryption: ddb.TableEncryption.CUSTOMER_MANAGED, encryptionKey: core.dataKey,
      timeToLiveAttribute: 'expiration',
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: stage === 'prod' ? RemovalPolicy.RETAIN : RemovalPolicy.DESTROY,
    });

    const powertools = lambda.LayerVersion.fromLayerVersionArn(this, 'Powertools',
      ssm.StringParameter.valueForStringParameter(this, '/aws/service/powertools/python/arm64/python3.12/latest'));
    const deps = new lambda.LayerVersion(this, 'Deps', {
      code: lambda.Code.fromAsset(path.join(ROOT, '.build/chaintrack/deps')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12], compatibleArchitectures: [lambda.Architecture.ARM_64],
      description: 'cryptography, pyyaml (arm64)',
    });
    const code = lambda.Code.fromAsset(path.join(ROOT, '.build/chaintrack/app'));

    const env = {
      STAGE: stage,
      TABLE_NAME: core.table.tableName,
      SIGNING_KEY_ARN: core.signingKey.keyArn,
      PHONE_HMAC_KEY_ARN: core.phoneHmacKey.keyArn,
      DATA_KEY_ARN: core.dataKey.keyArn,
      EVIDENCE_BUCKET: core.evidenceBucket.bucketName,
      DIGEST_BUCKET: core.digestBucket.bucketName,
      POLICY_STORE_ID: core.policyStoreId,
      IDEMPOTENCY_TABLE: idemTable.tableName,
      MODEL_ID_PARAM: modelParam.parameterName,
      BEDROCK_REGION: props.bedrockRegion,
      WEB_URL: props.webUrl,
      WA_NUMBER: props.waNumber,
      WA_PHONE_NUMBER_ID: props.waPhoneNumberId,
      POWERTOOLS_SERVICE_NAME: 'chaintrack',
      POWERTOOLS_LOG_LEVEL: 'INFO',
    };
    const fn = (name: string, handler: string, timeout = 20, memory = 512) => {
      const logGroup = new logs.LogGroup(this, `${name}Logs`, {
        logGroupName: `/aws/lambda/oae-${stage}-${name}`, retention: logs.RetentionDays.ONE_MONTH,
        removalPolicy: RemovalPolicy.DESTROY,
      });
      const f = new lambda.Function(this, name, {
        functionName: `oae-${stage}-${name}`,
        runtime: lambda.Runtime.PYTHON_3_12, architecture: lambda.Architecture.ARM_64,
        handler, code, layers: [powertools, deps], environment: env,
        timeout: Duration.seconds(timeout), memorySize: memory,
        tracing: lambda.Tracing.ACTIVE, logGroup,
      });
      nag(f, 'AwsSolutions::AwsSolutions-L1', 'CONTRACT §2 fixes Python 3.12 for both apps.');
      return f;
    };

    const api = fn('capture-api', 'capture.handlers.api.handler', 29);
    const transcribeDone = fn('transcribe-done', 'capture.handlers.transcribe_done.handler', 60);
    const digest = fn('ledger-digest', 'ledger.handlers.digest_job.handler', 120, 1024);

    // --- permissions (least privilege; no DeleteItem on the ledger for anyone) ---------------
    const ledgerRw = new iam.PolicyStatement({
      actions: ['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:UpdateItem', 'dynamodb:Query', 'dynamodb:ConditionCheckItem'],
      resources: [core.table.tableArn, `${core.table.tableArn}/index/*`],
    });
    for (const f of [api, transcribeDone]) {
      f.addToRolePolicy(ledgerRw);
      f.addToRolePolicy(new iam.PolicyStatement({ actions: ['kms:Sign', 'kms:GetPublicKey'], resources: [core.signingKey.keyArn] }));
      f.addToRolePolicy(new iam.PolicyStatement({ actions: ['kms:GenerateMac'], resources: [core.phoneHmacKey.keyArn] }));
      f.addToRolePolicy(new iam.PolicyStatement({ actions: ['verifiedpermissions:IsAuthorized'],
        resources: [`arn:aws:verifiedpermissions::${this.account}:policy-store/${core.policyStoreId}`] }));
      f.addToRolePolicy(new iam.PolicyStatement({ actions: ['ssm:GetParameter'], resources: [modelParam.parameterArn] }));
      f.addToRolePolicy(new iam.PolicyStatement({ actions: ['bedrock:InvokeModel'], resources: [
        'arn:aws:bedrock:*::foundation-model/*',
        `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
      ] }));
      core.dataKey.grantEncryptDecrypt(f);
      core.evidenceBucket.grantRead(f);
      core.evidenceBucket.grantPut(f);   // no DeleteObject: evidence is never removed by the app (audio/ expires by lifecycle)
      core.digestBucket.grantRead(f);
    }
    // TransactWriteItems is authorised per item action above (PutItem/UpdateItem).
    api.addToRolePolicy(new iam.PolicyStatement({
      actions: ['transcribe:StartTranscriptionJob', 'transcribe:TagResource'],
      resources: [`arn:aws:transcribe:${this.region}:${this.account}:transcription-job/oae-${stage}-*`],
    }));
    idemTable.grantReadWriteData(api);

    digest.addToRolePolicy(new iam.PolicyStatement({ actions: ['dynamodb:Scan'], resources: [core.table.tableArn] }));
    digest.addToRolePolicy(new iam.PolicyStatement({ actions: ['kms:Sign', 'kms:GetPublicKey'], resources: [core.signingKey.keyArn] }));
    core.dataKey.grantEncryptDecrypt(digest);
    core.digestBucket.grantPut(digest);

    for (const f of [api, transcribeDone, digest]) {
      nag(f.role!, 'AwsSolutions::AwsSolutions-IAM4[Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole]',
        'Basic execution role only grants CloudWatch Logs writes for this function.');
    }

    // --- WhatsApp via End User Messaging Social (only once a number is linked) -------------
    if (props.waPhoneNumberId) {
      const topic = new sns.Topic(this, 'WhatsAppInbound', {
        topicName: `oae-${stage}-whatsapp-inbound`, masterKey: core.dataKey, enforceSSL: true,
      });
      topic.addToResourcePolicy(new iam.PolicyStatement({
        principals: [new iam.ServicePrincipal('social-messaging.amazonaws.com')],
        actions: ['sns:Publish'], resources: [topic.topicArn],
        conditions: { StringEquals: { 'aws:SourceAccount': this.account } },
      }));
      core.dataKey.grantEncryptDecrypt(new iam.ServicePrincipal('social-messaging.amazonaws.com'));
      const wa = fn('whatsapp-ingest', 'ingest.handler.handler', 60);
      topic.addSubscription(new subs.LambdaSubscription(wa));
      for (const f of [wa, transcribeDone]) {
        f.addToRolePolicy(new iam.PolicyStatement({
          actions: ['social-messaging:SendWhatsAppMessage', 'social-messaging:GetWhatsAppMessageMedia'],
          resources: [props.waPhoneNumberId],
        }));
        f.addToRolePolicy(new iam.PolicyStatement({ actions: ['kms:Encrypt', 'kms:Decrypt'], resources: [core.dataKey.keyArn] }));
      }
      wa.addToRolePolicy(ledgerRw);
      for (const st of [
        new iam.PolicyStatement({ actions: ['kms:Sign', 'kms:GetPublicKey'], resources: [core.signingKey.keyArn] }),
        new iam.PolicyStatement({ actions: ['kms:GenerateMac'], resources: [core.phoneHmacKey.keyArn] }),
        new iam.PolicyStatement({ actions: ['verifiedpermissions:IsAuthorized'], resources: [`arn:aws:verifiedpermissions::${this.account}:policy-store/${core.policyStoreId}`] }),
        new iam.PolicyStatement({ actions: ['ssm:GetParameter'], resources: [modelParam.parameterArn] }),
        new iam.PolicyStatement({ actions: ['bedrock:InvokeModel'], resources: ['arn:aws:bedrock:*::foundation-model/*', `arn:aws:bedrock:*:${this.account}:inference-profile/*`] }),
        new iam.PolicyStatement({ actions: ['transcribe:StartTranscriptionJob', 'transcribe:TagResource'], resources: [`arn:aws:transcribe:${this.region}:${this.account}:transcription-job/oae-${stage}-*`] }),
      ]) wa.addToRolePolicy(st);
      core.evidenceBucket.grantRead(wa);
      core.evidenceBucket.grantPut(wa);
      nag(wa.role!, 'AwsSolutions::AwsSolutions-IAM4[Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole]',
        'Basic execution role only grants CloudWatch Logs writes for this function.');
      new CfnOutput(this, 'WhatsAppTopicArn', { value: topic.topicArn, description: 'Set as the event destination of the WABA in the EUMS console' });
    }

    // --- Transcribe completion -> draft READY (no Lambda sleeps) ---------------------------
    new events.Rule(this, 'TranscribeDone', {
      ruleName: `oae-${stage}-transcribe-done`,
      eventPattern: {
        source: ['aws.transcribe'], detailType: ['Transcribe Job State Change'],
        detail: { TranscriptionJobName: [{ prefix: `oae-${stage}-` }], TranscriptionJobStatus: ['COMPLETED', 'FAILED'] },
      },
      targets: [new targets.LambdaFunction(transcribeDone, { retryAttempts: 2 })],
    });

    // --- Nightly digest at 00:15 IST ----------------------------------------------------------
    const schedRole = new iam.Role(this, 'DigestScheduleRole', { assumedBy: new iam.ServicePrincipal('scheduler.amazonaws.com') });
    digest.grantInvoke(schedRole);
    new scheduler.CfnSchedule(this, 'NightlyDigest', {
      name: `oae-${stage}-nightly-digest`,
      scheduleExpression: 'cron(15 0 * * ? *)', scheduleExpressionTimezone: 'Asia/Kolkata',
      flexibleTimeWindow: { mode: 'OFF' },
      target: { arn: digest.functionArn, roleArn: schedRole.roleArn, input: '{}' },
    });

    // --- HTTP API -----------------------------------------------------------------------------
    const accessLogs = new logs.LogGroup(this, 'ApiAccessLogs', {
      logGroupName: `/aws/apigateway/oae-${stage}-capture`, retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: RemovalPolicy.DESTROY,
    });
    const http = new apigw.HttpApi(this, 'HttpApi', {
      apiName: `oae-${stage}-capture`,
      corsPreflight: {
        allowOrigins: props.webOrigins,
        allowMethods: [apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST, apigw.CorsHttpMethod.OPTIONS],
        allowHeaders: ['authorization', 'content-type', 'idempotency-key'],
        maxAge: Duration.hours(1),
      },
    });
    // addStage() on an API without its default stage fails to synth in aws-cdk-lib 2.273
    // ("SectionAlreadyContains"), so configure the default stage through its L1 resource.
    const cfnStage = http.defaultStage!.node.defaultChild as apigw.CfnStage;
    cfnStage.defaultRouteSettings = { throttlingRateLimit: 20, throttlingBurstLimit: 40 };
    cfnStage.accessLogSettings = {
      destinationArn: accessLogs.logGroupArn,
      format: JSON.stringify({ requestId: '$context.requestId', ip: '$context.identity.sourceIp', route: '$context.routeKey',
        status: '$context.status', latency: '$context.responseLatency', error: '$context.error.message' }),
    };
    const integ = new apigwi.HttpLambdaIntegration('CaptureInteg', api);
    const jwt = new apigwa.HttpUserPoolAuthorizer('Cognito', core.userPool, {
      userPoolClients: [core.captureClient],
      identitySource: ['$request.header.Authorization'],
    });
    const secured: [string, apigw.HttpMethod][] = [
      ['/chat/messages', apigw.HttpMethod.POST], ['/chat/drafts/{draft_id}', apigw.HttpMethod.GET],
      ['/chat/drafts/{draft_id}/confirm', apigw.HttpMethod.POST], ['/handovers', apigw.HttpMethod.POST],
      ['/batches/{batch_id}/events', apigw.HttpMethod.POST], ['/batches/{batch_id}', apigw.HttpMethod.GET],
      ['/batches/{batch_id}/lineage', apigw.HttpMethod.GET], ['/evidence/presign', apigw.HttpMethod.POST],
    ];
    const open: [string, apigw.HttpMethod][] = [
      ['/r/{token}', apigw.HttpMethod.GET], ['/confirm/{token}', apigw.HttpMethod.GET],
      ['/confirm/{token}', apigw.HttpMethod.POST], ['/verify/{batch_id}', apigw.HttpMethod.GET],
      ['/digests/latest', apigw.HttpMethod.GET], ['/digests/{date}', apigw.HttpMethod.GET],
    ];
    for (const [p, m] of secured) http.addRoutes({ path: p, methods: [m], integration: integ, authorizer: jwt });
    for (const [p, m] of open) {
      for (const r of http.addRoutes({ path: p, methods: [m], integration: integ })) {
        nag(r.node.defaultChild!, 'AwsSolutions::AwsSolutions-APIG4',
          'Public by design: receipts, handler confirmation (the single-use token is the credential) and chain verification need no account.');
      }
    }
    this.apiUrl = http.apiEndpoint + '/';

    // --- documented cdk-nag acknowledgements for wildcard grants ---------------------------------
    const coreName = core.stackName;
    const iam5: [string, string][] = [
      ['Action::kms:GenerateDataKey*', 'CDK grantEncryptDecrypt on the stage data key only (S3/DynamoDB SSE-KMS).'],
      ['Action::kms:ReEncrypt*', 'CDK grantEncryptDecrypt on the stage data key only.'],
      ['Action::s3:Abort*', 'Multipart abort on the stage evidence/digest bucket only.'],
      ['Action::s3:GetBucket*', 'Read access scoped to the stage evidence/digest bucket.'],
      ['Action::s3:GetObject*', 'Read access scoped to the stage evidence/digest bucket.'],
      ['Action::s3:List*', 'Read access scoped to the stage evidence/digest bucket.'],
      ['Resource::*', 'X-Ray PutTraceSegments/PutTelemetryRecords do not support resource-level permissions.'],
      [`Resource::${coreName}:ExportsOutputFnGetAttCaptureEvidenceF3503689ArnA9CECC03/*`, 'Objects in the stage capture evidence bucket.'],
      [`Resource::${coreName}:ExportsOutputFnGetAttLedgerB7379752Arn8FB7B3DC/index/*`, 'GSI2 (party timeline) on the stage ledger table.'],
      [`Resource::${coreName}:ExportsOutputFnGetAttLedgerDigests681569D3ArnC882635C/*`, 'Objects in the stage Object Lock digest bucket.'],
      ['Resource::arn:aws:bedrock:*::foundation-model/*', 'Model chosen at runtime from SSM; cross-region inference profiles route to several regions.'],
      ['Resource::arn:aws:bedrock:*:<AWS::AccountId>:inference-profile/*', 'Model chosen at runtime from SSM (inference profile).'],
      [`Resource::arn:aws:transcribe:ap-south-1:<AWS::AccountId>:transcription-job/oae-${stage}-*`, 'Only this stage\'s job-name prefix.'],
      ['Resource::<ledgerdigestE0127BFD.Arn>:*', 'Scheduler may invoke any version of the digest function.'],
    ];
    for (const [k, why] of iam5) nag(this, `AwsSolutions::AwsSolutions-IAM5[${k}]`, why);

    new ssm.StringParameter(this, 'ApiUrlParam', { parameterName: `/openaeye/${stage}/capture/api-url`, stringValue: this.apiUrl });
    new CfnOutput(this, 'ApiUrl', { value: this.apiUrl });
    new CfnOutput(this, 'DigestFunction', { value: digest.functionName });
  }
}
