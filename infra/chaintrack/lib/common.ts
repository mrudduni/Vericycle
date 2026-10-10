import { IConstruct } from 'constructs';
import { Validations } from 'aws-cdk-lib';

export interface StageProps {
  stage: string;
}

/** Acknowledge one cdk-nag finding on a construct, always with a written reason. */
export function nag(scope: IConstruct, id: string, reason: string): void {
  Validations.of(scope).acknowledge({ id, reason });
}

export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
