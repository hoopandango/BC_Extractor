from __future__ import annotations

import datetime
from dataclasses import dataclass

@dataclass
class Event:
	ID: int = None
	dates: list[datetime.datetime] = None
	versions: tuple[int] = None
	sched: str = None
	sched_data: dict = None
	name: str = None
	text: str = None

@dataclass
class EventGroup:
	events: list[Event]
	dates: list[datetime.datetime]
	name: str

@dataclass
class Gatya(Event):
	rates: list[float] = None
	rate_ups: dict[str, int] = None
	diff: list[list[str]] = None
	page: str = None
	slot: int = None
	guarantee: list[bool] = None
	extras: list[str] = None
	exclusives: list[str] = None

@dataclass
class Stage(Event):
	@staticmethod
	def fromEvent(e: Event) -> Stage:
		return Stage(**e.__dict__)

@dataclass
class Sale(Event):
	@staticmethod
	def fromEvent(e: Event) -> Sale:
		return Sale(**e.__dict__)

@dataclass
class Mission(Event):
	@staticmethod
	def fromEvent(e: Event) -> Mission:
		return Mission(**e.__dict__)

@dataclass
class RawStageGroup(Event):
	IDs: list[int] = None
	