"""ClaimGuard: a pure-Python, offline-testable recycling-claim checker.

No module under this package imports boto3 or any AWS SDK. Lambda handlers
live in ../handlers/ and call into this package; they are the only place
AWS clients appear. See docs/team/CONTRACT.md for the schema this package
implements.
"""
