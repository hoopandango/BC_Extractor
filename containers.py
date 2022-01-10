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
	dates: list[int]
	group_name: str

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
