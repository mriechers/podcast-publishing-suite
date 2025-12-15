# Code Review Guide: Efficiency & Model Selection Optimization

## Purpose

This guide helps you work with your local coding agent to audit codebases for:
1. **Token usage efficiency** - Where are we burning expensive LLM calls unnecessarily?
2. **Model selection opportunities** - Which tasks could use cheaper models?
3. **Workflow optimization** - How can we restructure to minimize LLM dependency?
4. **Automation potential** - What repetitive work can be eliminated?

Use this to build a roadmap of optimization work your local agent can execute.

---

## Part 1: Token Usage Audit

### Discovery Questions

Ask your agent to analyze the codebase and answer:

#### 1.1 Current LLM Interaction Points
```
"Identify every place in this codebase where we call an LLM or AI service. 
For each interaction, document:
- What model/service is being called?
- What is the input size (approximate tokens)?
- What is the output size (approximate tokens)?
- How often is this called? (per session, per day, per month)
- Is the call synchronous (blocking) or async?
- What happens if the call fails?"
```

**Expected output:** Inventory of all LLM touchpoints with cost estimates

#### 1.2 Token Consumption Hot Spots
```
"Rank our LLM interactions by total monthly token consumption.
Calculate: (input_tokens + output_tokens) × frequency × cost_per_token

For the top 5 consumers, analyze:
- Why is this consuming so many tokens?
- Is the full context necessary for the task?
- Could we cache results?
- Could we preprocess to reduce input size?
- Could we use a cheaper model?"
```

**Expected output:** Prioritized list of optimization targets

#### 1.3 Context Bloat Analysis
```
"For each LLM call, analyze what we're including in context:
- How much of the context is actually relevant to the task?
- Are we including entire files when we only need excerpts?
- Are we repeating the same context across multiple calls?
- Could we summarize or compress context first?
- Are we maintaining conversation history that's no longer relevant?"
```

**Expected output:** Specific opportunities to reduce context size

#### 1.4 Repeated vs. Unique Operations
```
"Identify operations where we call the LLM with similar/identical inputs:
- Are we processing the same files multiple times?
- Are we asking similar questions repeatedly?
- Could results be cached and reused?
- Could we batch similar operations?
- Should we build a lookup table instead?"
```

**Expected output:** Caching and batching opportunities

---

## Part 2: Model Selection Audit

### Discovery Questions

#### 2.1 Task Complexity Classification
```
"For each LLM interaction, classify the task complexity:

HIGH COMPLEXITY (requires Sonnet 4 or Opus):
- Requires creative judgment or editorial decisions
- Needs deep reasoning or multi-step analysis
- Involves nuanced language or style matching
- Requires understanding context across many documents
- Strategic planning or architecture decisions

MEDIUM COMPLEXITY (could use Sonnet 3.5 or GPT-4):
- Structured data transformation
- Code generation from clear specifications
- Summarization of well-defined content
- Question answering from provided context
- Basic content generation with templates

LOW COMPLEXITY (could use Haiku, GPT-3.5, or Gemini Flash):
- Text formatting and cleanup
- Data validation and extraction
- Simple classification tasks
- Template filling
- Regex-like operations
- Format conversions

ZERO COMPLEXITY (should be deterministic code):
- Fixed transformations
- Simple parsing
- Lookup operations
- Basic validation rules
- File I/O operations

For each task, explain why it's at that complexity level."
```

**Expected output:** Complexity classification for all LLM tasks

#### 2.2 Model Capabilities Mapping
```
"For each task currently using an expensive model, evaluate if a cheaper model could handle it:

Available models in our stack:
- Claude Opus 4 (~$75/MTok output) - Reserved for highest-value work
- Claude Sonnet 4.5 (~$15/MTok output) - Our primary workhorse
- Claude Haiku 3.5 (~$1.25/MTok output) - Fast, cheap, capable
- GPT-4 (~$30/MTok output) - Work-funded fallback
- GPT-3.5 (~$1.50/MTok output) - Work-funded for simple tasks
- Gemini 1.5 Pro (~$1.25/MTok output) - Education license, long context
- Gemini 1.5 Flash (~$0.15/MTok output) - Ultra-cheap for simple tasks

For each task, recommend:
1. Current model being used
2. Cheapest model that could handle it reliably
3. Estimated monthly savings from downgrade
4. Risk assessment (what could go wrong?)
5. Validation strategy (how to ensure quality?)
"
```

**Expected output:** Model downgrade opportunities with cost/risk analysis

#### 2.3 Multi-Model Pipeline Opportunities
```
"Identify workflows where we could chain cheaper → expensive models:

Pattern: Use cheap model for preprocessing, expensive model for final decisions

Examples:
- Haiku formats text → Sonnet makes editorial choices
- Gemini extracts structure → Claude writes final content
- GPT-3.5 generates first draft → Sonnet refines for style

For each workflow, propose:
1. Pipeline stages with model assignments
2. Data format between stages
3. Validation checkpoints
4. Fallback strategies if cheap model fails
5. Estimated cost savings"
```

**Expected output:** Multi-model pipeline architectures

#### 2.4 Model-Agnostic Interface Design
```
"Review our LLM integration code. Do we have:
- A standardized interface for LLM calls?
- Easy model swapping via configuration?
- A/B testing capability to compare models?
- Cost tracking per model/task combination?
- Retry logic that can fall back to different models?

If not, propose an abstraction layer that enables:
1. Easy model experimentation
2. Cost-aware routing
3. Performance monitoring
4. Graceful degradation"
```

**Expected output:** Architecture for model abstraction and routing

---

## Part 3: Workflow Optimization Audit

### Discovery Questions

#### 3.1 Human-in-the-Loop Analysis
```
"Identify all places where we wait for human input/approval:
- What decisions require human judgment?
- What are we asking humans to validate?
- Could we provide better defaults to reduce decisions?
- Could we batch decisions to reduce interruptions?
- Are we asking for unnecessary approvals?

For each human touchpoint, classify:
- ESSENTIAL: Truly requires human judgment
- PREFERENCE: Could be automated with good defaults
- VALIDATION: Could be spot-checked instead of every time
- UNNECESSARY: Could be fully automated"
```

**Expected output:** Opportunities to streamline human involvement

#### 3.2 Preprocessing Opportunities
```
"What data preparation happens before LLM calls?
- File format conversions
- Text cleaning and normalization
- Metadata extraction
- Structure identification
- Duplicate detection

For each preprocessing step:
- Is it currently done by LLM? (expensive!)
- Could it be deterministic code? (free!)
- Could it use a cheaper model?
- Could results be cached?
- Could it run async/batch overnight?"
```

**Expected output:** Preprocessing tasks to move out of expensive models

#### 3.3 Post-Processing Opportunities
```
"What happens after LLM responses?
- Formatting output
- Validating structure
- Extracting specific fields
- Applying business rules
- Saving to files/databases

For each post-processing step:
- Is validation happening via LLM? (wasteful!)
- Could we use structured output instead?
- Could we validate with deterministic code?
- Are we making a second LLM call to fix the first?
- Could we use templates to guarantee format?"
```

**Expected output:** Post-processing tasks to move out of LLMs

#### 3.4 Incremental vs. Batch Processing
```
"Review our processing patterns:
- What do we process one-at-a-time?
- What do we process in batches?
- What's processed in real-time vs. async?

For each workflow, analyze:
- Does this need immediate results?
- Could we batch multiple items together?
- Could this run overnight?
- Are we reprocessing unchanged inputs?
- Could we use incremental updates?"
```

**Expected output:** Batching and scheduling opportunities

---

## Part 4: Automation Potential Audit

### Discovery Questions

#### 4.1 Repetitive Pattern Detection
```
"Analyze task logs/history to find patterns:
- What LLM calls have nearly identical inputs?
- What questions get asked repeatedly?
- What tasks follow the same sequence every time?
- What decisions could be encoded as rules?

For each pattern:
- How many times does this happen per month?
- Could we create a template or script?
- Could we build a lookup table?
- Could we cache the result?
- Could we make it a CLI command?"
```

**Expected output:** Automation targets with frequency data

#### 4.2 Template & Snippet Opportunities
```
"What content do we generate repeatedly?
- Email templates
- Document structures
- Code boilerplate
- Metadata formats
- Common responses

For each template opportunity:
- What varies vs. what's consistent?
- Could we use string templates instead of LLM?
- Could we create a snippet library?
- Could we build a form/wizard?
- How much would this save per month?"
```

**Expected output:** Template library specifications

#### 4.3 Validation Rule Extraction
```
"What validation currently requires LLM calls?
- Format checking
- Content standards compliance
- Required field verification
- Style guide adherence
- Quality thresholds

For each validation task:
- Can we express this as deterministic rules?
- Can we use regex or parsing instead?
- Can we create a checklist/schema?
- Should we build a linter?
- When do we truly need LLM judgment?"
```

**Expected output:** Validation rules that can be automated

#### 4.4 Decision Tree Extraction
```
"What decisions do we make with LLM assistance?
- Routing/classification decisions
- Priority assignments
- Quality assessments
- Recommendation selection

For each decision point:
- What factors influence the decision?
- Could we build a decision tree?
- Could we use a scoring system?
- When is LLM judgment actually needed?
- Could we train a simple classifier?"
```

**Expected output:** Decision logic that could be deterministic

---

## Part 5: Architecture Review

### Discovery Questions

#### 5.1 Separation of Concerns
```
"Review the architecture for LLM-related code:
- Is LLM logic mixed with business logic?
- Can we swap models easily?
- Can we test without calling real APIs?
- Is error handling consistent?
- Are retry strategies implemented?

Evaluate against these principles:
- Single Responsibility: Each module has one job
- Dependency Injection: LLM client is injected, not hardcoded
- Interface Segregation: Different LLM tasks use specific interfaces
- Open/Closed: Easy to add new models without changing existing code

Recommend architectural improvements."
```

**Expected output:** Architecture refactoring roadmap

#### 5.2 Error Handling & Resilience
```
"Analyze how we handle LLM failures:
- What happens when API is down?
- What happens when response is malformed?
- What happens when we hit rate limits?
- Do we have circuit breakers?
- Do we have fallback strategies?

For each failure mode:
- How do we currently handle it?
- What's the user experience?
- Could we degrade gracefully?
- Should we retry with different model?
- Should we cache last-known-good result?"
```

**Expected output:** Resilience improvement recommendations

#### 5.3 Monitoring & Observability
```
"What visibility do we have into LLM usage?
- Do we log all calls with metadata?
- Do we track token consumption?
- Do we measure response times?
- Do we monitor costs in real-time?
- Do we track success/failure rates?
- Do we measure output quality?

Design a monitoring system that provides:
1. Real-time cost tracking
2. Usage patterns by task type
3. Model performance comparison
4. Alert thresholds (cost, latency, errors)
5. Monthly reporting and trends"
```

**Expected output:** Monitoring infrastructure specification

#### 5.4 Configuration Management
```
"Review how we configure LLM behavior:
- Are prompts hardcoded or externalized?
- Can we A/B test different prompts?
- Can we version prompts?
- Can we adjust model parameters without code changes?
- Can we feature-flag new model integrations?

Recommend configuration architecture that enables:
1. Easy prompt experimentation
2. Model parameter tuning
3. Feature flags for gradual rollouts
4. Cost limit enforcement
5. Usage quota management"
```

**Expected output:** Configuration management design

---

## Part 6: Documentation & Knowledge Gaps

### Discovery Questions

#### 6.1 Implicit Knowledge Audit
```
"What knowledge about LLM usage exists only in people's heads?
- Which prompts work well for which tasks?
- What are the failure modes and workarounds?
- When should we use which model?
- What preprocessing improves results?
- What post-processing is needed?

Create documentation for:
1. Model selection decision tree
2. Prompt engineering best practices (for this codebase)
3. Common failure modes and solutions
4. Cost optimization techniques we've learned
5. Quality assessment criteria"
```

**Expected output:** Documentation gaps to fill

#### 6.2 Onboarding Knowledge
```
"What does a new developer need to know about LLM usage in this codebase?
- How is the system architected?
- Where are the integration points?
- How do you add a new LLM task?
- How do you test without burning tokens?
- How do you monitor cost and quality?

Create onboarding guide covering:
1. Architecture overview with diagrams
2. Quick start for common tasks
3. Testing strategies
4. Debugging techniques
5. Cost management practices"
```

**Expected output:** Onboarding documentation specification

#### 6.3 Decision Rationale Capture
```
"Why did we make the LLM integration choices we did?
- Why these models vs. alternatives?
- Why this architecture pattern?
- Why these prompt structures?
- What did we try that didn't work?

Document the decisions and rationale so:
1. We don't repeat failed experiments
2. We can revisit decisions when context changes
3. New team members understand the 'why'
4. We can evaluate if assumptions still hold"
```

**Expected output:** Architecture decision records (ADRs)

---

## Part 7: Cost-Benefit Analysis Framework

### Analysis Template

For each optimization opportunity identified above, calculate:

```
"For [specific optimization]:

CURRENT STATE:
- Token consumption: X input + Y output tokens
- Frequency: Z times per [day/week/month]
- Current model: [model name] at $W per MTok
- Monthly cost: $___

PROPOSED STATE:
- Token consumption: X' input + Y' output tokens
- Frequency: Z' times per [day/week/month]  
- Proposed model: [model name] at $W' per MTok
- Monthly cost: $___

SAVINGS:
- Monthly cost reduction: $___
- Annual savings: $___
- Token reduction: ___%

IMPLEMENTATION COST:
- Development time: ___ hours
- Testing time: ___ hours
- Documentation time: ___ hours
- Total effort: ___ hours at $___ per hour = $___

ROI:
- Payback period: ___ months
- 12-month net benefit: $___
- Risk level: [Low/Medium/High]
- Priority: [High/Medium/Low]

DEPENDENCIES:
- Required before: [other work]
- Blocks: [other work]
- Can be done independently: [yes/no]
"
```

**Use this to prioritize your roadmap.**

---

## Part 8: Generating the Optimization Roadmap

### Final Synthesis

After working through Parts 1-7 with your agent, synthesize into a prioritized roadmap:

```
"Based on all the analysis above, create an optimization roadmap with three tiers:

QUICK WINS (Do first - High impact, low effort):
1. [Optimization name]
   - Impact: $___/month savings or X% token reduction
   - Effort: ___ hours
   - Risk: Low
   - Implementation: [brief description]

STRATEGIC IMPROVEMENTS (Do soon - High impact, medium effort):
1. [Optimization name]
   - Impact: $___/month savings or X% token reduction
   - Effort: ___ hours
   - Risk: Medium
   - Implementation: [brief description]
   - Dependencies: [what needs to happen first]

LONG-TERM INVESTMENTS (Do eventually - Medium impact, high effort):
1. [Optimization name]
   - Impact: $___/month savings or X% token reduction
   - Effort: ___ hours
   - Risk: High
   - Implementation: [brief description]
   - Dependencies: [what needs to happen first]

ESTIMATED TOTAL IMPACT:
- Monthly savings: $___
- Annual savings: $___
- Token reduction: ___%
- Total implementation time: ___ hours
- Net benefit (12 months): $___
"
```

---

## Using This Guide

### Recommended Workflow

**Step 1: Initial Audit (2-3 hours)**
- Run Parts 1-3 with your local agent
- Get the landscape of current LLM usage
- Identify obvious inefficiencies

**Step 2: Deep Dive (1-2 hours per part)**
- Work through Parts 4-6 for detailed analysis
- Let agent propose specific solutions
- Validate proposals against your domain knowledge

**Step 3: Prioritization (1 hour)**
- Use Part 7 to calculate ROI for each opportunity
- Build roadmap with Part 8
- Identify dependencies and sequence

**Step 4: Incremental Implementation**
- Start with Quick Wins to build momentum
- Measure actual savings vs. projected
- Adjust strategy based on results

### Working with Your Local Agent

**Effective prompting:**
```
"I want to audit this codebase for LLM efficiency. 
Let's work through the Code Review Guide systematically.

Start with Part 1: Token Usage Audit
First, answer question 1.1 about LLM interaction points.
Give me specific examples from the code with line numbers.
Format your response as a markdown table for easy review."
```

**Iterative refinement:**
```
"Thanks for that analysis. I see you identified 8 LLM calls.
Now for question 1.2: rank these by monthly token consumption.
Show your cost calculations.
Assume we make 1000 API calls per month with typical inputs."
```

**Building the roadmap:**
```
"Based on everything we've analyzed, create an optimization roadmap.
Prioritize by ROI (savings / implementation effort).
Format as: Quick Wins, Strategic Improvements, Long-term Investments.
For each item, give me a one-paragraph implementation plan."
```

### What Success Looks Like

After applying this guide, you should have:

✅ **Clear visibility** into where tokens are being consumed
✅ **Specific opportunities** to use cheaper models  
✅ **Concrete automation** targets that eliminate LLM dependency
✅ **Prioritized roadmap** with effort and savings estimates
✅ **Architecture improvements** that make optimization easier
✅ **Documentation** that prevents future inefficiency

**Target outcomes:**
- 30-50% reduction in monthly token usage
- 40-60% cost reduction through better model selection
- 20-30% of current LLM tasks automated away
- Clear routing logic: right task → right model
- Monitoring infrastructure that prevents cost surprises

---

## Appendix: Model Selection Decision Tree

Use this quick reference when evaluating tasks:

```
START: What are we trying to do?

├─ Creative/Editorial Decision?
│  ├─ YES → Claude Sonnet 4 or Opus 4
│  └─ NO → Continue ↓
│
├─ Requires >100k tokens context?
│  ├─ YES → Gemini 1.5 Pro (1M context, cheap)
│  └─ NO → Continue ↓
│
├─ Simple classification/extraction?
│  ├─ YES → Gemini Flash or Haiku 3.5
│  └─ NO → Continue ↓
│
├─ Code generation/refactoring?
│  ├─ YES → Copilot or GPT-4 (work-funded)
│  └─ NO → Continue ↓
│
├─ Could this be deterministic code?
│  ├─ YES → Write code, don't use LLM!
│  └─ NO → Continue ↓
│
├─ Format conversion/cleanup?
│  ├─ YES → Haiku 3.5 or GPT-3.5
│  └─ NO → Continue ↓
│
├─ Summarization/synthesis?
│  ├─ Short (<4k tokens) → GPT-3.5 (work-funded)
│  ├─ Long (>4k tokens) → Gemini Pro (cheap long context)
│  └─ Style-specific → Claude Sonnet 4
│
└─ Complex reasoning/planning?
   └─ YES → Claude Sonnet 4 or Opus 4
```

**Remember:** When in doubt, start with a cheaper model and upgrade only if quality is insufficient. Measure, don't assume.

---

## Ready to Start?

Pick a repository and begin with Part 1. Work through systematically with your local agent. Build your optimization roadmap. Then execute improvements incrementally, measuring savings as you go.

Good luck optimizing! 🎯