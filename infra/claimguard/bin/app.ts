#!/usr/bin/env node
import { App, Tags, Validations } from 'aws-cdk-lib';
import { AwsSolutionsChecks } from 'cdk-nag';
import { ClaimsStack } from '../lib/claims-stack';
import { ReviewWebStack } from '../lib/review-web-stack';
import { cap } from '../lib/common';

const app = new App();
const stage: string = app.node.tryGetContext('stage');
if (!stage || !/^[a-z][a-z0-9-]{1,15}$/.test(stage)) throw new Error('pass -c stage=<mrudduni|prod>');
if (stage === 'shaurya') throw new Error('stage "shaurya" belongs to the ChainTrack app; never deploy ClaimGuard there');
const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: 'ap-south-1' };
const ctx = (k: string, d = '') => String(app.node.tryGetContext(k) ?? d);
const webOrigins = ctx('webOrigins').split(',').map((s) => s.trim()).filter(Boolean);
// -c ledgerStage=<stage> reads that stage's ChainTrack ledger + Cognito (CONTRACT §2). Omit it to run on the demo fixture.
const ledgerStage = ctx('ledgerStage');
if (stage === 'prod' && !ledgerStage) throw new Error('prod must read the live ledger: pass -c ledgerStage=prod');

const S = cap(stage);
new ReviewWebStack(app, `OAE-${S}-ReviewWeb`, { env, stage });
new ClaimsStack(app, `OAE-${S}-Claims`, { env, stage, webOrigins, ledgerStage, webUrl: ctx('webUrl'), copilotModel: ctx('copilotModel') });

Tags.of(app).add('project', 'openaeye');
Tags.of(app).add('stage', stage);
Tags.of(app).add('owner', 'mrudduni');
Validations.of(app).addPlugins(new AwsSolutionsChecks(app));
