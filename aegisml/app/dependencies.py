from typing import Annotated

from fastapi import Depends

from app.inference import TicketClassifier, get_classifier


def classifier_dep() -> TicketClassifier:
    return get_classifier()


ClassifierDep = Annotated[TicketClassifier, Depends(classifier_dep)]
