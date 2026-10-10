#!/usr/bin/env node
import { App, Tags, Validations } from 'aws-cdk-lib';
import { AwsSolutionsChecks } from 'cdk-nag';
import { CoreStack } from '../lib/core-stack';
import { cap } from '../lib/common';

const app = new App();
const stage: string = app.node.tryGetContext('stage');
if (!stage || !/^[a-z][a-z0-9-]{1,15}$/.test(stage)) throw new Error('pass -c stage=<shaurya|prod>');
if (stage === 'mrudduni') throw new Error('stage "mrudduni" belongs to the ClaimGuard app; never deploy ChainTrack there');
const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: 'ap-south-1' };
const webOrigins = String(app.node.tryGetContext('webOrigins')).split(',').map((s) => s.trim()).filter(Boolean);
const digestRetentionDays = Number(app.node.tryGetContext('digestRetentionDays') ?? 1);
if (digestRetentionDays > 1 && !app.node.tryGetContext('approvedLongRetention')) {
  throw new Error('Object Lock retention > 1 day cannot be shortened later; needs Shaurya approval (-c approvedLongRetention=true)');
}

const S = cap(stage);
new CoreStack(app, `OAE-${S}-Core`, { env, stage, webOrigins, digestRetentionDays });

Tags.of(app).add('project', 'openaeye');
Tags.of(app).add('stage', stage);
Tags.of(app).add('owner', 'shaurya');
Validations.of(app).addPlugins(new AwsSolutionsChecks(app));
