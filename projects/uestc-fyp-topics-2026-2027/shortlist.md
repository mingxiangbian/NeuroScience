# UESTC FYP Final Shortlist 2026-2027

Date: 2026-07-02

This shortlist records the final six graduation project candidates selected from the 2026-2027 FYP topic announcement.

Selection basis:
- Prefer LLM / generative AI application systems, intelligent systems, runnable demos, and topics that can support a decent thesis.
- Avoid heavy PCB soldering, low-level hardware prototyping, RF/antenna/power electronics, medical AI, and small-car PID/path-planning style projects.
- Development-board deployment is acceptable if it mainly means software environment setup and model/application deployment, not circuit fabrication.

## Final Six

### English-Side Topics

| ID | Title | Supervisor | Email | Type | Fit Summary | Main Risk |
|---|---|---|---|---|---|---|
| 46 | Gen-LEAP: Generative AI for Learning, Engagement, Adaptation, and Personalisation | Sajjad Hussain(UK) | sajjad.hussain@glasgow.ac.uk | Software Simulation | Strong fit for generative AI application, learning assistant, personalization, and demo-oriented thesis work. | Scope is broad; needs teacher clarification on concrete system, data, and evaluation. |
| 28 | Human Activity Recognition using WiFi Channel State Information | Zhenghua Chen | Zhenghua.Chen@glasgow.ac.uk | Engineering Design, Case Study | Good sensor-intelligence topic using CSI time-series data and ML; no camera privacy issue and no PCB emphasis in the listing. | Requires signal processing/time-series understanding; experiments may be more technical than an LLM app. |
| 29 | Deep learning-based Machine Health Monitoring Systems under Practical Operating Conditions | Zhenghua Chen | Zhenghua.Chen@glasgow.ac.uk | Engineering Design, Case Study | Strong industrial AI / predictive maintenance topic. Good for model comparison, robustness, and thesis experiments. | "Machine health" means industrial equipment health, not medical AI; still needs sensor/time-series and practical-condition evaluation. |

### Chinese-Side Topics

| ID | Title | Supervisor | Email | Type | Fit Summary | Main Risk |
|---|---|---|---|---|---|---|
| 72 | Research and Implementation of Emotion Recognition System of Forum Text Based on LLM | 王玉林 | wyl@uestc.edu.cn | Engineering Design | Best Chinese-side fit for LLM/NLP application. Clear software direction, low hardware risk, and easy to build a runnable demo plus evaluation. | Need avoid shallow sentiment-classification-only work; should add explainability, bilingual comparison, or LLM-assisted analysis if scope allows. |
| 75 | Edge Intelligent Learning Assistant Based on Ascend AI Development Board | 郝家胜 | hao@uestc.edu.cn | Engineering Design | Strong fit for AI application system plus edge deployment. More distinctive than a normal web app because of Ascend board/local inference angle. | Highest board/deployment risk among selected Chinese topics; ask whether full model inference must run on Ascend or whether partial board-side validation is acceptable. |
| 74 / 2 | AI-Powered Multi-Course Homework Management and Intelligent Grading Assistant System Based on openEuler & Ascend | 郝家胜 | hao@uestc.edu.cn | Engineering Design | Practical AI education system with clearer requirements than #75: homework management, grading assistant, database/statistics, and testing. #2 and #74 are duplicate entries for the same topic. | Could become CRUD-heavy if not scoped carefully; also has openEuler/Ascend deployment risk, though likely less open-ended than #75. |

## Recommended Preference Order

### Chinese-Side

1. #72 - Best overall fit: LLM/NLP, software-first, low hardware risk.
2. #75 - Best for AI application plus edge deployment and resume distinctiveness.
3. #74 / #2 - Stable backup with clearer engineering scope, but less distinctive than #75.

### English-Side

1. #46 - Best fit for generative AI / learning assistant direction.
2. #29 - Strongest non-LLM research-engineering topic; good thesis potential.
3. #28 - Good intelligent sensing topic; slightly more signal-processing-heavy.

## Questions To Ask Supervisors

For #46:
- What exact system should be built: chatbot, adaptive learning path, RAG tutor, assessment assistant, or recommendation/personalization system?
- What dataset or user-study/evaluation method is expected?
- Are external LLM APIs allowed, or should the project use open-source/local models?

For #75:
- Is the Ascend development board mandatory for final deployment?
- Does the full model need to run on the board, or is partial edge inference / demo validation acceptable?
- What learning-assistant functions are expected beyond basic Q&A?

For #74 / #2:
- How much emphasis is on AI grading versus normal homework-management software?
- Is openEuler/Ascend deployment mandatory?
- What course types and assignment formats should be supported?

For #28:
- Will CSI data be provided, or does the student need to collect it?
- What activities and evaluation metrics are expected?

For #29:
- Will machine sensor datasets be provided?
- Is the expected focus robustness under changing operating conditions, model compression, or fault diagnosis accuracy?
