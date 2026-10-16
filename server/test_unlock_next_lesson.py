import unittest
from types import SimpleNamespace

from app.routers.functions import _unlock_next_lesson


class FakeSession:
    def __init__(self, lessons):
        self.lessons = lessons

    def exec(self, stmt):
        return self

    def all(self):
        return self.lessons

    def add(self, obj):
        return obj


class UnlockNextLessonTests(unittest.TestCase):
    def test_unlocks_first_non_completed_lesson_after_current(self):
        lessons = [
            SimpleNamespace(id='l1', status='completed', user_id='u1', roadmap_id='r1'),
            SimpleNamespace(id='l2', status='completed', user_id='u1', roadmap_id='r1'),
            SimpleNamespace(id='l3', status='locked', user_id='u1', roadmap_id='r1'),
            SimpleNamespace(id='l4', status='locked', user_id='u1', roadmap_id='r1'),
        ]

        session = FakeSession(lessons)
        next_id = _unlock_next_lesson(session, 'u1', 'r1', 'l1')

        self.assertEqual(next_id, 'l3')
        self.assertEqual(lessons[2].status, 'available')


if __name__ == '__main__':
    unittest.main()
