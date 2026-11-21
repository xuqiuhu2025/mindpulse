"""SafetyGuard 风险模式库（中文 + 英文）。

设计说明：
- 这是 MVP 的规则基线。正则规则可解释、可测试、可审计，
  但它不是自然语言理解，存在漏报/误报的已知限制（见 docs/SAFETY_DESIGN.md）。
- urgent 优先于 support；grief（哀伤）语境先剔除，避免“我朋友自杀了，我很难过”
  这类转述被误判为用户本人的即时风险。
- 口语化“想死你了 / 累死了 / 弄死这个 bug”等先作为安全短语剔除。
"""

import re

# ---------- 先剔除的安全短语（口语化误报防护） ----------
SAFE_SUBSTRINGS: tuple[str, ...] = (
    # 中文口语
    "想死你了", "累死了", "笑死了", "饿死了", "热死了", "冻死了", "吓死了",
    "吵死了", "烦死了", "忙死了", "无聊死了", "困死了", "丑死了", "慢死了",
    "弄死这个", "弄死它", "弄死个", "这个 bug 真想",
    # 英文口语
    "cut myself cooking", "cut my finger", "cut myself shaving",
    "miss you to death", "dying to see", "dying for a",
)

# ---------- 哀伤/转述语境（优先于 urgent 检测剔除） ----------
GRIEF_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        # 中文：亲友 + 自杀/离世
        r"(朋友|好友|家人|亲人|父亲|母亲|爸爸|妈妈|爷爷|奶奶|外公|外婆|姥姥|姥爷|叔叔|阿姨|舅舅|姑妈|同事|同学|老师|邻居|猫|狗|宠物|患者|来访者)[^。！？,，]{0,12}(自杀|轻生|离世|去世|过世|走了|走了)",
        # 英文：my <person> + died/suicide
        r"my (friend|best friend|father|mother|mom|dad|brother|sister|grandpa|grandma|uncle|aunt|cousin|dog|cat|pet|teacher|coworker|colleague|patient)[^.;!?]{0,30}"
        r"(suicide|suicided|killed (himself|herself|themselves)|passed away|passed|died|is gone)",
    )
)

# ---------- urgent：明确自伤/他伤意图、方法、计划或已采取行动 ----------
URGENT_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "self_harm_intent": tuple(
        re.compile(p, re.IGNORECASE)
        for p in (
            r"自杀", r"自尽", r"轻生", r"寻死", r"不想活", r"活不下去", r"想死",
            r"结束自己的生命", r"结束这一切", r"结束生命", r"了结自己", r"了结生命",
            r"kill myself", r"kill myself", r"end(ing)? my life", r"want to die", r"wanna die",
            r"suicid", r"take my own life", r"no reason to live", r"better off dead",
            r"don'?t want to (be alive|live) anymore", r"not want to be here anymore",
        )
    ),
    "self_harm_method": tuple(
        re.compile(p, re.IGNORECASE)
        for p in (
            r"割腕", r"割脉", r"划开手腕", r"用?刀割(自己|手腕)", r"上吊", r"跳楼", r"跳桥",
            r"从(楼上|桥上|天台|窗户)跳", r"烧炭", r"吞药", r"吞下(大量|整瓶)", r"服药自尽",
            r"安眠药自杀", r"吃(了|下)整瓶", r"过量服用", r"放血", r"勒(自己|脖子)",
            r"hang myself", r"slit my wrists", r"cut my wrists", r"jump off (the |a )?(roof|bridge|building|balcony)",
            r"overdose", r"take (all|the whole|every) (pill|tablet)", r"a hundred pills", r"carbon monoxide",
            r"painless way to die", r"how (do|to|can) i (kill|end) myself", r"ways to (kill myself|die)",
            r"how much (of|many).{0,20}(pill|dose|药)",
        )
    ),
    "harm_others": tuple(
        re.compile(p, re.IGNORECASE)
        for p in (
            r"杀死(他|她|他们|她们|人|别人)", r"(想|要|去|打算|计划)(杀|捅|砍|毒)(死)?(人|他|她|别人)",
            r"(想|要|打算|计划|准备)(去)?(杀|捅|砍|毒|勒|开枪)(死|了|掉)?(他|她|人|别人|老板|同学|同事|室友)",
            r"捅死", r"砍死", r"毒死", r"报复社会", r"伤害(别人|他人|路人)",
            r"kill (him|her|them|someone|people|my (boss|wife|husband|ex))", r"murder", r"stab (him|her|someone)",
            r"hurt (someone|people|others)", r"shoot (him|her|them|up|someone)", r"go on a (shooting|rampage)",
        )
    ),
    "immediate_action": tuple(
        re.compile(p, re.IGNORECASE)
        for p in (
            r"已经吞(了|下)", r"已经割(了|开)", r"已经吃(了|下)(整瓶|大量|药)", r"已经站在",
            r"(现在|此刻)(就)?站在", r"刚(刚)?(吞|割|跳)", r"手里拿着(刀|药|绳)", r"(买|藏)好了?刀", r"写好了?遗书", r"遗书(写|放)好",
            r"已经跳", r"我现在就去(做|死|跳|割)", r"马上就(去|跳|割|吞)",
            r"i already took", r"i (have )?just took", r"i have taken (the |my )?(pills|medication)",
            r"i swallowed", r"i already cut", r"i am standing on", r"standing on the (edge|roof|bridge)",
            r"i'?m about to (jump|do it)", r"i wrote (a |my )?(goodbye|suicide) note", r"the pills are already",
            r"i (have|'ve) already (done it|taken)",
        )
    ),
}

# ---------- support：持续低落 / 强烈焦虑 / 无助感（无明确危险表达） ----------
SUPPORT_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "persistent_low_mood": tuple(
        re.compile(p, re.IGNORECASE)
        for p in (
            r"抑郁", r"情绪低落", r"很低落", r"一直低落", r"提不起劲", r"提不起兴趣", r"没兴趣(做|了)",
            r"觉得(自己)?没用", r"觉得自己很失败", r"好失败", r"绝望", r"无助", r"撑不下去", r"撑不住",
            r"绷不住了", r"活着好累", r"生活没意思", r"没意思", r"压抑", r"内耗",
            r"(?<![a-zA-Z])emo(?![a-zA-Z])", r"破防",
            r"depressed", r"depression", r"hopeless", r"worthless", r"empty inside", r"no motivation",
            r"can'?t get out of bed", r"miserable", r"give up", r"what'?s the point",
        )
    ),
    "strong_anxiety_or_distress": tuple(
        re.compile(p, re.IGNORECASE)
        for p in (
            r"焦虑", r"恐慌", r"惊恐", r"心慌", r"喘不过气", r"崩溃", r"想哭", r"一直哭", r"失眠",
            r"睡不着", r"难过", r"伤心", r"紧张到", r"害怕", r"孤独", r"寂寞", r"迷茫", r"喘不上气",
            r"anxious", r"anxiety", r"panic (attack|attacks)", r"can'?t sleep", r"insomnia",
            r"breaking (down|point)", r"can'?t take it", r"so tired of", r"lonely", r"crying (a lot|all)",
            r"burn(ed|ing)? out", r"burnout", r"overwhelmed",
        )
    ),
}

# ---------- prompt injection：试图覆盖系统规则的输入 ----------
INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"忽略(之?前|以上|上面|先前|所有)(的)?(所有|全部)?(指令|说明|规则|设定|提示)",
        r"无视(之?前|以上|所有)(的)?(指令|规则)",
        r"ignore (all |any |the )?(previous|above|prior|earlier|your) (instructions|prompts|rules|directions)",
        r"disregard (your |all |the |any )?(previous |instructions|rules|guidelines|directions)",
        r"forget (your |all |everything|your training)",
        r"忘记(你的)?(规则|设定|训练|指令)",
        r"system\s*prompt", r"system\s*:",
        r"(你现在是|现在你是|扮演|假装你(是)?)(一个)?(没有限制|不受限制|无限制|DAN|没有任何规则)",
        r"jailbreak", r"越狱模式", r"开发者模式", r"DAN模式", r"do anything now",
        r"解除(所有)?(安全|内容|限制)", r"关闭(安全|审查|限制|规则|guard)",
        r"disable (safety|filters?|restrictions?|guardrails?|rules)",
        r"你(现在)?不再受(任何)?(限制|规则)", r"你没有(任何)?(限制|规则)",
        r"pretend (you are|to be) (not|no longer)", r"act as if you (have no|are not)",
        r"roleplay as (an? )?(unrestricted|uncensored)", r"unrestricted ai", r"uncensored",
        r"提示词注入", r"prompt injection",
    )
)

# 信号类别 -> 对用户的解释（用于“为什么出现这条提示”，绝不写入原始文本）
CATEGORY_EXPLANATIONS: dict[str, str] = {
    "self_harm_intent": "检测到可能涉及自伤意图的表达",
    "self_harm_method": "检测到可能涉及自伤方法的表达",
    "harm_others": "检测到可能涉及伤害他人的表达",
    "immediate_action": "检测到可能已经采取行动或迫在眉睫的表达",
    "persistent_low_mood": "检测到持续低落相关的表达",
    "strong_anxiety_or_distress": "检测到强烈焦虑或痛苦相关的表达",
    "prompt_injection": "检测到试图改变系统规则的输入",
}
