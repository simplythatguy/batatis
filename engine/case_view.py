"""The existing derived read views, all evaluated against one immutable case revision."""
from .models import Case


def current_case(case: Case) -> Case:
    if case.intake is None and case.identify is None and case.relevance is None:
        return case
    view = case.model_copy(deep=True)
    if view.intake is not None:
        from .intake import service
        from .intake.questions import issued_questions
        if view.intake.plan is None:
            service.refresh(view)
        else:
            view.intake.plan.asked = issued_questions(view.facts, view.intake.plan)
    if view.identify is not None:
        from .routes_identify import _current
        view.identify = _current(view.identify, view)
    if view.relevance is not None:
        from .relevance import current_record
        view.relevance = current_record(view.relevance, view)
    return view
