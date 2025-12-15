[ Skip to main content ](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/#main-content) AI Agent best practices from one year as AI Engineer : r/AI_Agents
Open menu Open navigation [ ](https://www.reddit.com/)Go to Reddit Home
r/AI_Agents A chip A close button
[ Log In ](https://www.reddit.com/login/)Log in to Reddit
Expand user menu Open settings menu
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) Go to AI_Agents  ](https://www.reddit.com/r/AI_Agents/)
[r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
• 4mo ago
[LearnSkillsFast](https://www.reddit.com/user/LearnSkillsFast/)
[Português (Brasil)](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=pt-br)[简体中文](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=zh-hans)[Русский](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=ru)[日本語](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=ja)[Français](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=fr)[Tiếng Việt](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=vi)[Polski](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=pl)[Português (Portugal)](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=pt-pt)[Norsk (Bokmål)](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=no)[Español (Latinoamérica)](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=es-419)[Filipino](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=fil)
#  AI Agent best practices from one year as AI Engineer 
[ Tutorial  ](https://www.reddit.com/r/AI_Agents/?f=flair_name%3A%22Tutorial%22)
Hey everyone. 
# I've worked as an AI Engineer for 1 year (6 total as a dev) and have a RAG project on GitHub with almost 50 stars. While I'm not an expert (it's a very new field!), here are some important things I have noticed and learned.
​First off, you might **not need an AI agent**. I think a lot of AI hype is shifting towards AI agents and touting them as the "most intelligent approach to AI problems" especially judging by how people talk about them on Linkedin. 
AI agents are great for **open-ended problems** where the number of steps in a workflow is difficult or impossible to predict, like a chatbot. 
However, if your workflow is more clearly defined, you're usually better off with a simpler solution: 
  * Creating a **chain in LangChain**. 
  * Directly using an **LLM API** like the OpenAI library in Python, and building a workflow yourself 


A lot of this advice I learned from Anthropic's "Building Effective Agents". 
# If you need more help understanding what are good AI agent use-cases, I will leave a good resource in the comments
If you  _do_ need an agent, you generally have three paths: 
  1. **No-code agent building:** (I haven't used these, so I can't comment much. But I've heard about n8n? maybe someone can chime in?). 
  2. **Writing the agent yourself** using LLM APIs directly (e.g., OpenAI API) in Python/JS. **Anthropic recommends this approach.**
  3. **Using a library like LangGraph** to create agents. Honestly, **this is what I recommend for beginners** to get started. 


Keep in mind that LLM best practices are still evolving rapidly (even the founder of LangGraph has acknowledged this on a podcast!). Based on my experience, here are some general tips: 
  * **Optimize Performance, Speed, and Cost:**
    * Start with the **biggest/best model** to establish a performance baseline. 
    * Then, **downgrade to a cheaper model** and observe when results become unsatisfactory. This way, you get the best model at the best price for your specific use case. 
    * You can use tools like OpenRouter to easily switch between models by just changing a variable name in your code. 
  * **Put limits on your LLM API's**
    * Seriously, I cost a client hundreds of dollars one time because I accidentally ran an LLM call too many times huge inputs, cringe. You can set spend limits on the OpenAI API for example. 
  * **Use Structured Output:**
    * Whenever possible, force your LLMs to produce **structured output**. With the OpenAI Python library, you can feed a schema of your desired output structure to the client. The LLM will then  _only_ output in that format (e.g., JSON), which is incredibly useful for passing data between your agent's nodes and helps **save on token usage**. 
  * **Narrow Scope & Single LLM Calls:**
    * Give your agent a **narrow scope of responsibility**. 
    * Each LLM call should generally **do one thing**. For instance, if you need to generate a blog post in Portuguese from your notes which are in English: one LLM call should generate the blog post, and  _another_ should handle the translation. This approach also makes your agent much **easier to test and debug**. 
    * For more complex agents, consider a multi-agent setup and splitting responsibility even further 
  * **Prioritize Transparency:**
    * Explicitly **show the agent's planning steps**. This transparency again makes it much easier to test and debug your agent's behavior. 


A lot of these findings are from Anthropic's Building Effective Agents Guide. I also made a video summarizing this article. Let me know if you would like to see it and I will send it to you. 
What's missing? 
Read more 
Share 
#  Related Answers Section 
Related Answers 
[ Best practices for LLM agents deployment  ](https://www.reddit.com/answers/ffd3cd68-1144-4993-a600-1d2d9780061d/?q=Best%20practices%20for%20LLM%20agents%20deployment&source=PDP)
[ Tips for writing AI agents  ](https://www.reddit.com/answers/d1ff53e6-9405-4c6f-8c43-0932cb36ac0d/?q=Tips%20for%20writing%20AI%20agents&source=PDP)
[ Future trends in AI agents  ](https://www.reddit.com/answers/1957ce2e-136f-4280-a5af-3a414051dadd/?q=Future%20trends%20in%20AI%20agents&source=PDP)
[ AI agents for application developers  ](https://www.reddit.com/answers/6b546b75-7ba4-43cc-a68c-2db77fb2aa08/?q=AI%20agents%20for%20application%20developers&source=PDP)
[ Building LLM agents  ](https://www.reddit.com/answers/3707b3d2-bb22-4112-8d46-393b0d23e7e8/?q=Building%20LLM%20agents&source=PDP)
New to Reddit? 
Create your account and connect with a world of communities. 
Continue with Email 
Continue With Phone Number 
By continuing, you agree to our [User Agreement](https://www.redditinc.com/policies/user-agreement) and acknowledge that you understand the [Privacy Policy](https://www.redditinc.com/policies/privacy-policy). 
#  More posts you may like 
  * [ How much can an AI Agent Engineer expect to make?  ](https://www.reddit.com/r/AI_Agents/comments/1lhtjpj/how_much_can_an_ai_agent_engineer_expect_to_make/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 5mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ How much can an AI Agent Engineer expect to make?  ](https://www.reddit.com/r/AI_Agents/comments/1lhtjpj/how_much_can_an_ai_agent_engineer_expect_to_make/)
2 upvotes · 13 comments 
* * *
  * [ I wrote an AI Agent that works better than I expected. Here are 10 learnings.  ](https://www.reddit.com/r/AI_Agents/comments/1m8vlzt/i_wrote_an_ai_agent_that_works_better_than_i/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 4mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ I wrote an AI Agent that works better than I expected. Here are 10 learnings.  ](https://www.reddit.com/r/AI_Agents/comments/1m8vlzt/i_wrote_an_ai_agent_that_works_better_than_i/)
196 upvotes · 71 comments 
* * *
  * [ What's the best resource to learn AI agent for a non-technical person?  ](https://www.reddit.com/r/AI_Agents/comments/1l0ivxv/whats_the_best_resource_to_learn_ai_agent_for_a/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 5mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ What's the best resource to learn AI agent for a non-technical person?  ](https://www.reddit.com/r/AI_Agents/comments/1l0ivxv/whats_the_best_resource_to_learn_ai_agent_for_a/)
56 upvotes · 37 comments 
* * *
  * [ Which AI agent framework do you find most practical for real projects ?  ](https://www.reddit.com/r/AI_Agents/comments/1nfz717/which_ai_agent_framework_do_you_find_most/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 2mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Which AI agent framework do you find most practical for real projects ?  ](https://www.reddit.com/r/AI_Agents/comments/1nfz717/which_ai_agent_framework_do_you_find_most/)
66 upvotes · 68 comments 
* * *
  * [ Building Practical AI Agents: Lessons from 6 Months of Development  ](https://www.reddit.com/r/AI_Agents/comments/1jv0vuu/building_practical_ai_agents_lessons_from_6/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 7mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Building Practical AI Agents: Lessons from 6 Months of Development  ](https://www.reddit.com/r/AI_Agents/comments/1jv0vuu/building_practical_ai_agents_lessons_from_6/)
55 upvotes · 13 comments 
* * *
  * [ How to evaluate AI systems/ agents?  ](https://www.reddit.com/r/AI_Agents/comments/1isvh11/how_to_evaluate_ai_systems_agents/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 9mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ How to evaluate AI systems/ agents?  ](https://www.reddit.com/r/AI_Agents/comments/1isvh11/how_to_evaluate_ai_systems_agents/)
5 upvotes · 14 comments 
* * *
  * [ Is building an AI agent this easy?  ](https://www.reddit.com/r/AI_Agents/comments/1nokpsd/is_building_an_ai_agent_this_easy/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 2mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Is building an AI agent this easy?  ](https://www.reddit.com/r/AI_Agents/comments/1nokpsd/is_building_an_ai_agent_this_easy/)
39 upvotes · 67 comments 
* * *
  * [ Why do you roll your own AI Agent Framework?  ](https://www.reddit.com/r/AI_Agents/comments/1o0bx3j/why_do_you_roll_your_own_ai_agent_framework/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 1mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Why do you roll your own AI Agent Framework?  ](https://www.reddit.com/r/AI_Agents/comments/1o0bx3j/why_do_you_roll_your_own_ai_agent_framework/)
23 upvotes · 41 comments 
* * *
  * [ AI Experts please help! What is the best way I can learn AI and build AI Agents?  ](https://www.reddit.com/r/AI_Agents/comments/1n4nf8n/ai_experts_please_help_what_is_the_best_way_i_can/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 2mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ AI Experts please help! What is the best way I can learn AI and build AI Agents?  ](https://www.reddit.com/r/AI_Agents/comments/1n4nf8n/ai_experts_please_help_what_is_the_best_way_i_can/)
78 upvotes · 47 comments 
* * *
  * [ What are the best AI Agents for data analysis?  ](https://www.reddit.com/r/AI_Agents/comments/1mzutfw/what_are_the_best_ai_agents_for_data_analysis/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 3mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ What are the best AI Agents for data analysis?  ](https://www.reddit.com/r/AI_Agents/comments/1mzutfw/what_are_the_best_ai_agents_for_data_analysis/)
16 upvotes · 23 comments 
* * *
  * [ Gimme a exhaustive list of AI Agent Builders  ](https://www.reddit.com/r/AI_Agents/comments/1oac95z/gimme_a_exhaustive_list_of_ai_agent_builders/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 24d ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Gimme a exhaustive list of AI Agent Builders  ](https://www.reddit.com/r/AI_Agents/comments/1oac95z/gimme_a_exhaustive_list_of_ai_agent_builders/)
4 upvotes · 20 comments 
* * *
  * [ My guide on the mindset you absolutely MUST have to build effective AI agents  ](https://www.reddit.com/r/AI_Agents/comments/1ilw77c/my_guide_on_the_mindset_you_absolutely_must_have/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 9mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ My guide on the mindset you absolutely MUST have to build effective AI agents  ](https://www.reddit.com/r/AI_Agents/comments/1ilw77c/my_guide_on_the_mindset_you_absolutely_must_have/)
314 upvotes · 45 comments 
* * *
  * [ Developers building AI agents - what are your biggest challenges?  ](https://www.reddit.com/r/AI_Agents/comments/1kf4qgx/developers_building_ai_agents_what_are_your/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 6mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Developers building AI agents - what are your biggest challenges?  ](https://www.reddit.com/r/AI_Agents/comments/1kf4qgx/developers_building_ai_agents_what_are_your/)
46 upvotes · 51 comments 
* * *
  * [ Want to build an AI agent — where do we start?  ](https://www.reddit.com/r/AI_Agents/comments/1m7716d/want_to_build_an_ai_agent_where_do_we_start/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 4mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Want to build an AI agent — where do we start?  ](https://www.reddit.com/r/AI_Agents/comments/1m7716d/want_to_build_an_ai_agent_where_do_we_start/)
69 upvotes · 76 comments 
* * *
  * [ Anyone who builds AI agents professionally or running an agency ?  ](https://www.reddit.com/r/AI_Agents/comments/1mnbklw/anyone_who_builds_ai_agents_professionally_or/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 3mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Anyone who builds AI agents professionally or running an agency ?  ](https://www.reddit.com/r/AI_Agents/comments/1mnbklw/anyone_who_builds_ai_agents_professionally_or/)
24 upvotes · 31 comments 
* * *
  * [ What’s the most underrated use case of AI agents you’ve seen or tried?  ](https://www.reddit.com/r/AI_Agents/comments/1nps2cc/whats_the_most_underrated_use_case_of_ai_agents/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 2mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ What’s the most underrated use case of AI agents you’ve seen or tried?  ](https://www.reddit.com/r/AI_Agents/comments/1nps2cc/whats_the_most_underrated_use_case_of_ai_agents/)
17 upvotes · 46 comments 
* * *
  * [ Which is most preferred way for everyone build AI agents?  ](https://www.reddit.com/r/AI_Agents/comments/1m750w4/which_is_most_preferred_way_for_everyone_build_ai/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 4mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Which is most preferred way for everyone build AI agents?  ](https://www.reddit.com/r/AI_Agents/comments/1m750w4/which_is_most_preferred_way_for_everyone_build_ai/)
12 upvotes · 35 comments 
* * *
  * [ I'm done with AI agent frameworks, but it is a great learning curve to understand how to make effective agents  ](https://www.reddit.com/r/AI_Agents/comments/1o0rg8b/im_done_with_ai_agent_frameworks_but_it_is_a/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 1mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ I'm done with AI agent frameworks, but it is a great learning curve to understand how to make effective agents  ](https://www.reddit.com/r/AI_Agents/comments/1o0rg8b/im_done_with_ai_agent_frameworks_but_it_is_a/)
16 upvotes · 21 comments 
* * *
  * [ What’s the best way to get serious about building AI agents?  ](https://www.reddit.com/r/AI_Agents/comments/1n1xn3k/whats_the_best_way_to_get_serious_about_building/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 3mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ What’s the best way to get serious about building AI agents?  ](https://www.reddit.com/r/AI_Agents/comments/1n1xn3k/whats_the_best_way_to_get_serious_about_building/)
27 upvotes · 23 comments 
* * *
  * [ What skills to hire for, for building AI agents?  ](https://www.reddit.com/r/AI_Agents/comments/1lln9gj/what_skills_to_hire_for_for_building_ai_agents/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 5mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ What skills to hire for, for building AI agents?  ](https://www.reddit.com/r/AI_Agents/comments/1lln9gj/what_skills_to_hire_for_for_building_ai_agents/)
18 upvotes · 36 comments 
* * *
  * [ Why AI agents fail in production.  ](https://www.reddit.com/r/AI_Agents/comments/1o64p1y/why_ai_agents_fail_in_production/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 1mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Why AI agents fail in production.  ](https://www.reddit.com/r/AI_Agents/comments/1o64p1y/why_ai_agents_fail_in_production/)
22 comments 
* * *
  * [ Building Your First AI Agent  ](https://www.reddit.com/r/AI_Agents/comments/1kfs50g/building_your_first_ai_agent/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 6mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Building Your First AI Agent  ](https://www.reddit.com/r/AI_Agents/comments/1kfs50g/building_your_first_ai_agent/)
77 upvotes · 28 comments 
* * *
  * [ Lessons Learned from Building AI Agents  ](https://www.reddit.com/r/AI_Agents/comments/1l4otey/lessons_learned_from_building_ai_agents/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 5mo ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Lessons Learned from Building AI Agents  ](https://www.reddit.com/r/AI_Agents/comments/1l4otey/lessons_learned_from_building_ai_agents/)
45 upvotes · 8 comments 
* * *
  * [ Complete beginner looking for a roadmap to learn AI agents and automation, where do I start?  ](https://www.reddit.com/r/AI_Agents/comments/1om26dr/complete_beginner_looking_for_a_roadmap_to_learn/)
[ ![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=48&height=48&frame=1&auto=webp&crop=48%3A48%2Csmart&s=3ce4f5a0e73b11995a1e5c554b4116e16d05018d) r/AI_Agents ](https://www.reddit.com/r/AI_Agents/) • 10d ago
![r/AI_Agents icon](https://styles.redditmedia.com/t5_8b5cvj/styles/communityIcon_izy2luu72nee1.png?width=96&height=96&frame=1&auto=webp&crop=96%3A96%2Csmart&s=20cf99757a0ac0f6735e20e69bab9bb46f409207) [r/AI_Agents](https://www.reddit.com/r/AI_Agents/)
A place for discussion around the use of AI Agents and related tools. AI Agents are LLMs that have the ability to "use tools" or "execute functions" in an autonomous or semi-autonomous (also known as human-in-the-loop) fashion. Follow our event calendar: https://lu.ma/oss4ai Join us on Discord! https://discord.gg/6tGkQcFjBY 
* * *
233K Members
### [ Complete beginner looking for a roadmap to learn AI agents and automation, where do I start?  ](https://www.reddit.com/r/AI_Agents/comments/1om26dr/complete_beginner_looking_for_a_roadmap_to_learn/)
64 upvotes · 32 comments 
* * *


* * *
## 
View Post in 
[繁體中文 ](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=zh-hant)
[हिन्दी ](https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/?tl=hi)
Anyone can view, post, and comment to this community
0 0
[Reddit Rules](https://www.redditinc.com/policies/content-policy) [Privacy Policy](https://www.reddit.com/policies/privacy-policy) [User Agreement](https://www.redditinc.com/policies/user-agreement) [Accessibility](https://support.reddithelp.com/hc/sections/38303584022676-Accessibility) [Reddit, Inc. © 2025. All rights reserved.](https://redditinc.com)
Expand Navigation Collapse Navigation
![](https://id.rlcdn.com/472486.gif)
