Use the following context:

* AGENT.md
* docs/ai/skills/write-tests.md

Analyze the current tests for this module.

Step 1:
Summarize:

* what behaviors are currently covered
* what is NOT covered

Step 2:
Propose additional tests focusing on:

* real behavior (not implementation details)
* edge cases
* failure scenarios
* CLI behavior (if applicable)

Step 3:
Implement the tests with these constraints:

* no network access
* use in-memory data (e.g., pandas DataFrames)
* mock only external boundaries

At the end:

* explain what each new test validates
