from meetinglog.domain import AnalysisForm, Contract


class FormOption(Contract):
    id: AnalysisForm
    title: str
    description: str


FORMS = [
    FormOption(
        id="meeting",
        title="회의 정리",
        description="논의 내용, 합의, 할 일과 남은 질문을 정리해요.",
    ),
    FormOption(
        id="interview",
        title="인터뷰 정리",
        description="질문과 답변, 핵심 발언과 서로 다른 의견을 정리해요.",
    ),
    FormOption(
        id="project",
        title="프로젝트 논의",
        description="요구사항, 범위, 제약과 후속 할 일을 정리해요.",
    ),
]

INSTRUCTIONS = {
    "meeting": "회의 정리 폼이다. 논의 흐름, 명시한 합의와 후속 할 일을 중심으로 정리한다. 제안과 확정 사항을 구분한다.",
    "interview": "인터뷰 정리 폼이다. 질문과 답변, 답변의 조건과 핵심 발언을 중심으로 정리한다. 인터뷰 답변을 합의나 할 일로 바꾸지 않는다.",
    "project": "프로젝트 논의 폼이다. 요구사항, 작업 범위, 제약, 변경 사항과 후속 할 일을 주제별로 정리한다. 확정되지 않은 일정·예산·구현 방법은 미정으로 남긴다.",
}
