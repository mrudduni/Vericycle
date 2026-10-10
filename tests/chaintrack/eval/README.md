# Extraction eval set

`transcripts.jsonl` holds transcripts and the expected extraction. Rows marked `"synthetic": true`
were written by the agent to test the pipeline. **Replace or extend them with transcripts of real
voice notes** (Shaurya and friends, with consent; Hindi, Hinglish, English, at least one noisy).
Store only the transcript and the expected JSON here, never the audio.

Run against Bedrock (needs AWS credentials):

    python scripts/chaintrack/run_eval.py --model <model-id>

Target (SHAURYA.md §5): `count` exact on at least 9 of 10; the prompt-injection row (t08) must
still give count 5.
