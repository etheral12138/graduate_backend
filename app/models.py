from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class Answer(BaseModel):
    answer_a: str
    answer_b: str
    answer_c: str
    answer_d: str
    answer_e: Optional[str] = None
    answer_f: Optional[str] = None

class CorrectAnswers(BaseModel):
    answer_a_correct: str
    answer_b_correct: str
    answer_c_correct: str
    answer_d_correct: str
    answer_e_correct: str
    answer_f_correct: str

class Tag(BaseModel):
    name: str

class Question(BaseModel):
    id: int
    question: str
    description: str
    answers: Answer
    multiple_correct_answers: str
    correct_answers: CorrectAnswers
    correct_answer: Optional[str] = None
    explanation: str
    tip: Optional[str] = None
    tags: List[Tag]
    category: str
    difficulty: str

class QuizSession(BaseModel):
    id: str
    started_at: datetime
    question_count: int
    status: str
    score: Optional[int] = None
    completed_at: Optional[datetime] = None
