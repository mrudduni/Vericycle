import { CfnOutput, Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as amplify from 'aws-cdk-lib/aws-amplify';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { StageProps } from './common';

/** Amplify Hosting app for web-review (manual deploys from scripts/claimguard/deploy_web.sh; no repo connection). */
export class ReviewWebStack extends Stack {
  readonly webUrl: string;

  constructor(scope: Construct, id: string, props: StackProps & StageProps) {
    super(scope, id, props);
    const app = new amplify.CfnApp(this, 'ReviewWeb', {
      name: `oae-${props.stage}-review-web`,
      platform: 'WEB',
      customRules: [{
        source: '</^[^.]+$|\\.(?!(css|gif|ico|jpg|jpeg|js|png|txt|svg|webp|woff|woff2|ttf|map|json|webmanifest)$)([^.]+$)/>',
        target: '/index.html', status: '200',
      }],
      customHeaders: [
        'customHeaders:',
        '  - pattern: "**/*"',
        '    headers:',
        '      - key: Strict-Transport-Security',
        '        value: max-age=31536000; includeSubDomains',
        '      - key: X-Content-Type-Options',
        '        value: nosniff',
        '      - key: Referrer-Policy',
        '        value: no-referrer',
      ].join('\n'),
    });
    new amplify.CfnBranch(this, 'Main', { appId: app.attrAppId, branchName: 'main', stage: props.stage === 'prod' ? 'PRODUCTION' : 'DEVELOPMENT' });
    this.webUrl = `https://main.${app.attrDefaultDomain}`;
    new ssm.StringParameter(this, 'WebUrl', { parameterName: `/openaeye/${props.stage}/review/web-url`, stringValue: this.webUrl });
    new CfnOutput(this, 'AppId', { value: app.attrAppId });
    new CfnOutput(this, 'WebUrlOut', { value: this.webUrl });
  }
}
