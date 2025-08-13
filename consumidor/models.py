# models.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class Employee:
    perfil: str
    employee: str
    attendance_date: str
    attendance_time: str

@dataclass
class Student:
    perfil: str
    area: str
    customer: str
    student: str
    turma: str
    attendance_date: str
    attendance_time: str

@dataclass
class Assistido:
    perfil: str
    area: str
    customer: str
    attendance_date: str
    attendance_time: str
