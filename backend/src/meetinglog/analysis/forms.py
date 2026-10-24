from meetinglog.domain import AnalysisForm, AnalysisSection, Contract, FormAnalysisBody


class FormOption(Contract):
    id: AnalysisForm
    title: str
    description: str
    sections: list[str]


FORMS = [
    FormOption(
        id="meeting",
        title="일반 회의",
        description="안건별 논의와 결정, 후속 조치를 정리해요.",
        sections=["회의 결과", "안건별 논의", "후속 조치", "남은 쟁점"],
    ),
    FormOption(
        id="project",
        title="요구사항 협의",
        description="목표, 작업 범위, 제약과 미정 사항을 정리해요.",
        sections=[
            "목표",
            "요구사항",
            "포함 범위",
            "제외·보류 범위",
            "제약",
            "예산",
            "일정",
            "미정 사항",
            "후속 조치",
        ],
    ),
    FormOption(
        id="decision",
        title="검토와 결정",
        description="선택지와 판단 기준, 결정한 이유를 정리해요.",
        sections=["결정 결과", "판단 기준", "선택지 비교", "선택 이유", "남은 조건", "후속 조치"],
    ),
    FormOption(
        id="progress",
        title="진행 점검",
        description="업무별 진행 상태와 막힌 일, 다음 할 일을 정리해요.",
        sections=["현재 상태", "완료한 일", "진행 중인 일", "막힌 일·필요한 지원", "다음 할 일"],
    ),
    FormOption(
        id="interview",
        title="사용자 인터뷰",
        description="사용자의 경험과 문제, 현재 대응과 의견을 정리해요.",
        sections=[
            "사용자 상황",
            "경험과 문제",
            "현재 대응",
            "요구·의견",
            "추가 확인 사항",
            "후속 조치",
        ],
    ),
]

INSTRUCTIONS = {
    "meeting": "안건별로 논의와 결론을 묶는다. 회의 결과는 짧게 요약하고 안건별 논의와 같은 내용을 반복하지 않는다. 확정된 결정과 보류된 쟁점을 구분한다.",
    "project": "목표에는 해결할 문제와 달성하려는 결과를 기록한다. 요구사항에는 필요한 동작과 조건을 요구사항별로 묶는다. 포함 범위에는 이번에 구현하기로 한 기능을, 제외·보류 범위에는 제외한 기능과 나중에 검토할 기능을 구분해 적는다. 기술 선택과 운영 조건은 제약에 기록한다. 예산·일정은 희망인지 약속인지 확정인지 본문에 명시한다. 제안된 구현 방법을 확정 요구사항으로 바꾸지 않는다. 미정 사항에는 논의했지만 정하지 않은 쟁점을 적는다. 후속 조치에는 자료 확인·공유·견적 작성 등 명시된 모든 다음 행동을 actions로 기록한다. 언급 없는 목표·예산·일정은 빈 섹션으로 두거나 생략한다. 서버가 전체 분석 이후 언급 없음으로 표시한다.",
    "decision": "명시된 결정이나 미결정 상태는 반드시 결정 결과 섹션에 기록한다. 판단 기준·선택지·선택 이유·남은 조건을 구분한다. 비교 기준이 발언에 있고 비교할 선택지가 둘 이상이면 선택지 비교의 comparisons에 선택지별 행을 작성한다. 이 비교를 groups 문단으로 대신하지 않는다. 비교 기준이 없으면 선택지와 논의 내용만 groups에 기록한다. 각 points에 비용·성능·운영 등 실제 언급한 기준과 평가를 적는다. 가격·점수·장단점을 외부 지식으로 만들지 않는다. 결정되지 않았다면 제안이나 미결정 상태를 보존한다.",
    "progress": "업무 항목별로 완료·진행·막힌 상태를 구분한다. 현재 상태는 짧게 요약하고 업무 상세를 반복하지 않는다. 이전 회의 자료가 없으므로 이전 대비 변화와 진척률을 추정하지 않는다. 다음 할 일에는 대화에서 명시한 후속 행동만 넣는다.",
    "interview": "참여자가 설명한 실제 경험별로 상황·행동·문제·현재 대응을 묶는다. 경험에 대한 진술과 희망·의견을 구분한다. 경험 사례를 다른 섹션에서 반복하지 않는다. 참여자의 제안을 제품의 확정 요구사항으로 바꾸지 않는다. 한 사람의 경험을 전체 사용자의 경향으로 일반화하지 않는다. 음성에 없는 실제 조작·행동이나 숨은 심리를 추측하지 않는다. 추가 확인 사항에는 대화에서 미해결로 남은 내용만 넣는다.",
}


def option(form: AnalysisForm) -> FormOption:
    return next(item for item in FORMS if item.id == form)


def instruction(form: AnalysisForm) -> str:
    selected = option(form)
    return (
        f"양식: {selected.title}\n섹션 순서: {' → '.join(selected.sections)}\n"
        + INSTRUCTIONS[form]
        + "\n섹션 제목은 위 이름을 그대로 사용한다. 내용 없는 선택 섹션은 생략한다. "
        "groups는 주제별 문단이며 title은 필요한 경우에만 작성한다. "
        "comparisons는 검토와 결정 양식의 선택지 비교에서만 사용한다. "
        "actions는 후속 조치 또는 다음 할 일 섹션에만 작성한다. 같은 항목을 groups에 반복하지 않는다. "
        "AI가 새로 제안하는 개선안·질문·행동은 작성하지 않는다."
    )


def canonicalize(
    body: FormAnalysisBody, form: AnalysisForm, *, final: bool = True
) -> FormAnalysisBody:
    from meetinglog.analysis.grounding import GroundingError

    selected = option(form)
    sections = {}
    for section in body.sections:
        if section.title not in selected.sections or section.title in sections:
            raise GroundingError(
                "invalid_section",
                f"허용된 섹션을 중복 없이 사용한다: {', '.join(selected.sections)}",
            )
        if section.comparisons and (
            form != "decision" or section.title != "선택지 비교" or len(section.comparisons) < 2
        ):
            raise GroundingError(
                "invalid_comparison",
                "비교표는 검토와 결정의 선택지 비교에 둘 이상의 선택지가 있을 때만 작성한다.",
            )
        if section.actions and section.title not in ("후속 조치", "다음 할 일"):
            raise GroundingError(
                "invalid_actions", "actions는 후속 조치 또는 다음 할 일 섹션에 작성한다."
            )
        if section.title in ("후속 조치", "다음 할 일") and (section.groups or section.comparisons):
            raise GroundingError(
                "invalid_actions", "후속 조치와 다음 할 일은 groups 대신 actions에 작성한다."
            )
        sections[section.title] = section
    if not any(
        section.groups or section.comparisons or section.actions for section in body.sections
    ):
        raise GroundingError(
            "empty_analysis",
            "대화에서 확인할 수 있는 내용을 지정 양식에 정리한다. 빈 결과를 반환하지 않는다.",
        )
    required = {"목표", "예산", "일정"} if form == "project" and final else set()
    result = []
    for title in selected.sections:
        section = sections.get(title)
        if section and (section.groups or section.comparisons or section.actions):
            result.append(section)
        elif title in required:
            result.append(AnalysisSection(title=title))
    return FormAnalysisBody(sections=result)
