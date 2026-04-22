Use the following context:

* AGENT.md
* docs/ai/skills/code-review.md

Review the provided changes and evaluate:

1. Behavior

* Does it do exactly what was intended?
* Any unintended changes?

2. Architecture

* Are module boundaries respected?
* Any new coupling or hidden complexity?

3. Code Quality

* Is the implementation simple and explicit?
* Any unnecessary abstraction?

4. Tests

* Do tests validate real behavior?
* Are there weak or trivial assertions?

5. Documentation

* Does README match actual behavior?

Output:

* risks
* issues to fix
* what is safe to keep
* what should be reverted or simplified
