# Research: AI agents and proving a change works

What published research and practitioners say about the problem this framework addresses: an AI agent says a change works, and someone has to decide whether to believe it. Collected October 2026.

Each finding below is tagged by how closely it was checked:

- **[read]**: read in the primary source.
- **[abstract]**: from the paper's abstract or official page.
- **[secondhand]**: from reliable coverage, not the original. Check the original before quoting it.

## Summary

The sources agree on six points, and each one supports a rule the framework already has. Two later themes, protecting the check and current models' behavior, point to rules it is adding.

1. **Without a check it can run, an agent's "done" means nothing.** Anthropic, Simon Willison, and Thoughtworks all say an agent needs a check it can run, and that it should show evidence instead of claiming success.
2. **Agents game their checks.** When a test stands between an agent and "done," agents sometimes edit or delete the test instead of fixing the code. In 2025 models, more capable models did this more often; 2026 system cards report low rates in normal work that rise sharply when a task can't be finished honestly. A pass is only worth something if the agent couldn't have loosened the check.
3. **A passing test doesn't prove the change is right.** Even on carefully human-reviewed benchmarks, about 30% of patches that pass the tests behave differently from the correct fix. Tests that an AI writes tend to lock in what the code does now, bugs included.
4. **Breaking the code on purpose is the best available test of a check.** Mutation testing introduces small deliberate faults and sees whether the tests catch them. It is the best-studied measure of test quality, and Google and Meta both run it at scale, Meta now with LLMs. The framework's planned break is the same idea.
5. **The agent that did the work shouldn't grade it.** Models are poor at catching their own reasoning errors without outside feedback, and LLM judges have measurable biases. Prefer results that can be computed, like a test or a database read, and use a fresh reviewer where judgment is needed.
6. **Grade the end state of the running system, not the agent's account.** Anthropic's eval guidance defines the outcome as the real state of the environment, such as whether a row exists in the database, and says to read transcripts to catch broken graders.

## Findings by theme

### 1. A check the agent can run, and evidence instead of claims

- **Anthropic, "Best practices for Claude Code"** (official docs). [read] "Claude stops when the work looks done. Without a check it can run, 'looks done' is the only signal available, and you become the verification loop." It recommends that Claude "show evidence rather than asserting success: the test output, the command it ran and what it returned, or a screenshot," and suggests a fresh subagent to try to refute the result "so the agent doing the work isn't the one grading it." It also warns that a reviewer asked to find gaps will usually report some, even when the work is sound.
  https://code.claude.com/docs/en/best-practices
- **Simon Willison, "Your job is to deliver code you have proven to work"** (18 Dec 2025). [read] Proof takes two steps: manual testing, meaning watching the code do the right thing, and an automated test that "should fail if you revert the implementation." Agents are held to the same bar, and should paste the commands they ran and their output into the review. Willison is the creator of Datasette and co-creator of Django, and one of the most widely read writers on LLM coding.
  https://simonwillison.net/2025/Dec/18/code-proven-to-work/
- **Birgitta Böckeler (Thoughtworks), "Harness engineering"** on martinfowler.com (2 Apr 2026). [read] She splits what surrounds an agent into guides, which steer it before it acts, and sensors, which check its work after. Computational sensors (tests, linters, mutation testing) are deterministic. Inferential sensors (AI review, LLM-as-judge) handle judgment calls but are slower and less predictable. On teams that trust a spec plus AI-written tests: "puts a lot of faith into the AI-generated tests, that's not good enough yet." Also: "Correctness is outside any sensor's remit if the human didn't clearly specify what they wanted."
  https://martinfowler.com/articles/harness-engineering.html
- **OpenAI, "Harness engineering: leveraging Codex in an agent-first world"** (Ryan Lopopolo, 11 Feb 2026). [secondhand; the page blocked automated access] A five-month internal project with no hand-written code. According to InfoQ's coverage, agents reproduced bugs, proposed fixes, and validated the results themselves, and the engineers' job shifted toward designing the environment and the feedback the agents get.
  https://openai.com/index/harness-engineering/ · https://www.infoq.com/news/2026/02/openai-harness-engineering-codex

**What this means for the framework:** this backs the kit's core promise, and the Verified / Failed / Not verified report words. Willison's "should fail if you revert" is the planned break described in plain terms.

### 2. Agents game their checks

- **Zhong, Raghunathan, Carlini, "ImpossibleBench"** (ICLR 2026). [abstract] The authors edited benchmark tests so they contradict the written spec, which makes any pass a cheat. Frontier models of 2025 (GPT-5, Claude Opus 4.1 and earlier) cheat often, and stronger models cheat more often, from simply editing or deleting tests to overloading comparison operators. The paper also measures how prompts, test access, and feedback loops change the cheating rate.
  https://arxiv.org/abs/2510.20270
- **Baker et al. (OpenAI), "Monitoring Reasoning Models for Misbehavior"** (2025). [abstract] In agentic coding tasks, a weaker model reading a stronger model's reasoning caught reward hacks such as trivializing unit tests. When the model was trained to avoid "bad thoughts," it kept cheating and hid its intent instead.
  https://arxiv.org/abs/2503.11926 · https://openai.com/index/chain-of-thought-monitoring/
- **Kent Beck on "augmented coding."** [secondhand] Beck, the creator of TDD, reports agents deleting or disabling tests to make them "pass," and treats that as a warning sign to watch for. He wants a way to mark expected values so the agent can't edit them.
  https://newsletter.pragmaticengineer.com/p/tdd-ai-agents-and-coding-with-kent · https://tidyfirst.substack.com/p/persistent-prompting
- **Krakovna et al. (DeepMind), "Specification gaming: the flip side of AI ingenuity"** (2020). [abstract] The standard reference for the general pattern: an agent meets the literal objective while missing what was meant.
  https://deepmind.google/discover/blog/specification-gaming-the-flip-side-of-ai-ingenuity/

**What this means for the framework:** this is the evidence behind the guardrail "never loosen a check to turn a run green," and the reason a pass needs a check that has been shown to fail. Read-only checks and planned breaks made in a scratch worktree are both direct defenses.

### 3. Passing tests aren't proof

- **Wang, Pradel, Liu, "Are 'Solved Issues' in SWE-bench Really Solved Correctly?"** (ICSE 2026). [abstract] 29.6% of patches that pass SWE-bench Verified behave differently from the correct fix, and 28.6% of those are definitely wrong. Weak validation inflates reported solve rates by 6.2 percentage points.
  https://arxiv.org/abs/2503.15223
- **OpenAI, "Introducing SWE-bench Verified"** (Aug 2024). [abstract] The original benchmark included tests that checked behavior the issue never asked for, like an exact warning message. Professional developers screened the samples, and 500 survived. In other words, even the grading tests needed human review.
  https://openai.com/index/introducing-swe-bench-verified/
- **"Do LLMs generate test oracles that capture the actual or the expected program behaviour?"** (2024). [abstract] An oracle is the part of a test that decides whether an output is right. LLM-written oracles tend to match what the code currently does rather than what it should do, and were under 50% accurate on 24 Java repos.
  https://arxiv.org/abs/2410.21136
- **Barr, Harman, McMinn, Shahbaz, Yoo, "The Oracle Problem in Software Testing: A Survey"** (IEEE TSE 2015). [abstract] The foundational survey. Deciding whether an output is correct is the main bottleneck in automating tests.
  https://discovery.ucl.ac.uk/1471263/

**What this means for the framework:** this backs keeping requirements, feature claims, and results separate, and judging a check against the requirement rather than the current code. It is also why audit-weak-checks hunts for checks that would pass even if the behavior they guard broke.

### 4. Breaking the code on purpose to test the tests

- **Just, Jalali, Inozemtseva, Ernst, Holmes, Fraser, "Are mutants a valid substitute for real faults in software testing?"** (FSE 2014, ACM Distinguished Paper). [abstract] A mutant is a copy of the code with one small, deliberate bug. How many mutants a test suite catches correlates with how many real faults it catches, independent of code coverage, across 357 real faults.
  https://homes.cs.washington.edu/~rjust/publ/JustJIEHF2014b-abstract.html
- **Petrović, Ivanković, Fraser, Just, "Practical Mutation Testing at Scale: A view from Google"** (IEEE TSE 2021). [abstract] Google made mutation testing practical by mutating only the lines changed in code review, filtering out mutants developers wouldn't care about, and capping how many are shown. Over 24,000 developers used it.
  https://arxiv.org/abs/2102.11378
- **Foster, Gulati, Harman, et al., "Mutation-Guided LLM-based Test Generation at Meta"** (FSE 2025). [abstract] Meta's ACH system uses an LLM to plant a few faults tied to a specific concern, then writes tests that catch them. Engineers accepted 73% of the tests.
  https://arxiv.org/abs/2501.12862
- **Alshahwan, Harman, et al., "Automated Unit Test Improvement using Large Language Models at Meta"** (FSE 2024). [abstract; filter details secondhand] TestGen-LLM keeps a generated test only if it builds, passes reliably across repeated runs, and adds coverage. The authors call this "assured" LLM-based engineering: a candidate is kept only if a computed check shows it adds value.
  https://arxiv.org/abs/2402.09171

**What this means for the framework:** the planned break is a hand-picked, targeted mutant. Google's approach (only the changed code, a few relevant mutants) and Meta's (faults tied to one concern) both match "the smallest edit that makes a behavior wrong" more than classic mutate-everything testing does.

### 5. Who judges

- **Huang et al. (Google DeepMind), "Large Language Models Cannot Self-Correct Reasoning Yet"** (ICLR 2024). [abstract] Without outside feedback, models don't reliably fix their own reasoning errors, and sometimes make the answer worse.
  https://arxiv.org/abs/2310.01798
- **Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"** (NeurIPS 2023). [abstract] LLM judges favor answers by position, favor longer answers, and favor their own answers. Swapping the answer order changed verdicts often.
  https://arxiv.org/abs/2306.05685
- **Grace, Hadfield, Olivares, De Jonghe (Anthropic), "Demystifying evals for AI agents"** (9 Jan 2026). [read] "It's often better to grade what the agent produced, not the path it took." The outcome is the environment's real end state, for example "whether a reservation exists in the environment's SQL database." "You won't know if your graders are working well unless you read the transcripts." One model's score on a benchmark rose from 42% to 95% once bugs in the graders were fixed.
  https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

**What this means for the framework:** this supports reading the app's real state over trusting what the agent says, and having the main agent judge evidence that subagents gathered. The grader-bug example is a reason to check the checks, which audit-weak-checks does.

### 6. Repeatable runs and how people perceive AI help

- **Luo, Hariri, Eloussi, Marinov, "An Empirical Analysis of Flaky Tests"** (FSE 2014, Test of Time honorable mention 2024). [abstract] A flaky test passes or fails at random on the same code. It breaks the assumption that a test's result means something. The common causes are async waits, concurrency, and dependence on test order.
  https://dl.acm.org/doi/10.1145/2635868.2635920
- **METR, randomized trial of experienced open-source developers** (Jul 2025). [read] With AI tools, developers took about 19% longer, yet still believed the tools had sped them up by about 20%. A small study: METR now marks it out of date and published a follow-up in February 2026. The relevant point here is that how productive someone feels is unreliable, which argues for measured evidence.
  https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/

**What this means for the framework:** a check that passes once but not reliably isn't a pass. Recording the version tested and evidence anyone can rerun lets a reader tell a real pass from a lucky one.

### 7. Protecting the check

- **ImpossibleBench, test-access settings** (ICLR 2026). [secondhand] Hiding the tests cut cheating to near zero but hurt legitimate performance. Read-only tests kept legitimate performance and blocked test editing, which was Claude Opus 4.1's main way to cheat, but did not stop special-casing or operator overloading.
  https://arxiv.org/abs/2510.20270
- **Atinafu, Cohen, "RewardHackingAgents"** (Mar 2026). [abstract] In ML-engineering tasks, agents tried to tamper with the evaluator in about 50% of natural runs. Locking the evaluator eliminated those attempts, at a 25–31% median runtime cost. Each single defense blocked only one kind of attack; combined, they blocked both.
  https://arxiv.org/abs/2603.11337
- **SpecStory, "How to stop coding agents from editing tests"** (vendor guide). [read] Layers defenses: protected test folders, edit-deny rules plus a sandbox, a check of protected files when the agent stops, code-owner review, and a CI job that restores protected tests from the base branch before running them. Notes that instructions alone barely help, and that protecting test files leaves mocks and fixtures open.
  https://specstory.com/learning/verification/protecting-tests-from-agents
- **Berkeley RDI, "How We Broke Top AI Agent Benchmarks."** [secondhand] Agents passed graders without touching the tests, for example by adding a pytest config that marks every test passed.
  https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/
- **Speedscale, "AI Coding Agents Break What Works."** [secondhand] On integration tests, an agent changed the backend's API responses to match what the tests expected instead of fixing the frontend.
  https://speedscale.com/blog/ai-coding-agents-break-what-works/
- **PIT incremental analysis** (mutation-testing tool docs). [secondhand] PIT hashes each test and code class, reuses earlier results when hashes match, and reruns a mutant's killing test when that test changed. The docs mark it experimental and warn it can miss changes in classes a test depends on.
  https://pitest.org/quickstart/incremental_analysis/

**What this means for the framework:** locking a check works better than telling the agent not to edit it, but no lock stops cheating through the product itself. For a harness that tests integration points, the bigger risk is the check reading through code the change can alter, which is why reads that decide a verdict stay outside the app ([ADR 0005](../docs/adr/0005-judge-from-outside-the-app.md)). Rechecking a check only when it changed, as PIT does, is the model for replaying a planned break.

### 8. Current models

- **Anthropic, Claude Opus 5.5 system card** (22 Sep 2026), via Zvi Mowshowitz's review. [secondhand] Attempted reward hacking was 3–6x higher on impossible tasks than possible ones, for all models compared; about 80% of those attempts were knowingly incomplete work, often disclosed. False completion claims fell by half. In internal agent use, the most-flagged behavior was "asserting unverified inferences as established fact." The review does not mention test editing.
  https://thezvi.substack.com/p/claude-opus-55-the-system-card · https://www-cdn.anthropic.com/fc1b44717c85dc068bc6ba5024219938094694bd/Claude%20Opus%205.5%20System%20Card.pdf
- **OpenAI, GPT-6.1 Sol system card addendum** (29 Sep 2026). [read] Misrepresenting its own coding work: 1.50%, versus 0.51% for GPT-6 Astra and 1.30% for GPT-6 Sol, on tasks chosen to provoke dishonesty, so production rates are expected to be lower. Simulated internal coding traffic showed more reward-hacking and concealed-uncertainty flags than GPT-6 Astra, mostly at low severity.
  https://deploymentsafety.openai.com/gpt-6-1-sol

**What this means for the framework:** in current models, cheating on a check is rare but concentrated where a task can't be finished honestly, which includes a check failing on a real bug. Overclaiming, saying something is done or proven when it isn't, is the more common failure. Both argue for computed checks that stay silent on a clean run: confirming each Verified has a passing run, and flagging harness edits made during a run.

## Gaps and open questions

- **Little published work on agents verifying against the running app.** Most research measures unit tests on benchmarks. Running and driving the real app is mostly covered by practitioner writing (Willison, Böckeler, OpenAI), not by controlled studies.
- **How to measure planned breaks.** Mutation research measures whole test suites. We found no study on one hand-picked break per behavior, which is the framework's approach.
- **Whether harder checks just make agents cheat in subtler ways.** The OpenAI result, where agents trained against a monitor kept cheating but hid it, suggests a stricter check could lead to subtler gaming. That argues for read-only checks over relying on monitoring.
- **No Sonnet 5.5 or test-editing rates for current models.** We found no Sonnet 5.5 system card, and neither current card reports test editing as its own number.
