Subject: Re: proof, not monitoring

Hi {first_name},

Following up with one concrete thing instead of a nudge.

Here's the exact failure we prevent: an agent with elevated permissions takes an action in your environment. Sixty days later your auditor (or a regulator) asks what it was authorized to do and what it actually did. Today your answer is a log line and a shrug. With a11oy it's a signed receipt that verifies offline — tamper one byte and verification fails; remove evidence and the verdict is INCOMPLETE, never PASS.

OpenAI just shipped auto-review in Codex — pre-execution approval for elevated actions. That's the market validating the control point. What auto-review doesn't give you is the portable record: Codex auto-review decides. a11oy proves. The decision doesn't survive the vendor, the outage, or the auditor.

Still holding 2 design-partner slots this quarter. a11oy.net/pricing

Stephen
