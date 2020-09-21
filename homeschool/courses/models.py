import uuid
from typing import Optional

from django.db import models
from django.utils.functional import cached_property
from ordered_model.models import OrderedModel

from homeschool.core.compatibility import OrderedModelQuerySet
from homeschool.core.models import DaysOfWeekModel
from homeschool.schools.models import GradeLevel
from homeschool.users.models import User

from .exceptions import NoSchoolYearError


class Course(DaysOfWeekModel):
    """A course is a container for tasks in a certain subject area."""

    name = models.CharField(max_length=256)
    grade_levels = models.ManyToManyField(
        "schools.GradeLevel",
        related_name="courses",
        through="courses.GradeLevelCoursesThroughModel",
    )
    uuid = models.UUIDField(default=uuid.uuid4, db_index=True)
    default_task_duration = models.IntegerField(
        default=30, help_text="The default task duration in minutes"
    )

    @property
    def is_running(self):
        """Check if the course is running on any days of the week."""
        return self.days_of_week != self.NO_DAYS

    @cached_property
    def has_many_grade_levels(self):
        """Check if multiple grade levels are associated with the course."""
        return self.grade_levels.count() > 1

    @cached_property
    def school_year(self):
        """Get the school year for the course."""
        grade_level = self.grade_levels.select_related("school_year").first()
        if grade_level:
            return grade_level.school_year
        raise NoSchoolYearError("The course has no school year.")

    def belongs_to(self, user):
        """Check if the course belongs to the user."""
        grade_levels = GradeLevel.objects.filter(
            school_year__school__admin=user
        ).values_list("id", flat=True)
        return Course.objects.filter(id=self.id, grade_levels__in=grade_levels).exists()

    def __str__(self):
        return self.name


class GradeLevelCoursesThroughModel(OrderedModel):
    grade_level = models.ForeignKey("schools.GradeLevel", on_delete=models.CASCADE)
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE)
    order_with_respect_to = "grade_level"

    objects = models.Manager.from_queryset(OrderedModelQuerySet)()

    class Meta:
        ordering = ("grade_level", "order")


class CourseTask(OrderedModel):
    """A student's required action in a course."""

    class Meta(OrderedModel.Meta):
        pass

    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="course_tasks"
    )
    uuid = models.UUIDField(default=uuid.uuid4, db_index=True)
    description = models.TextField()
    duration = models.PositiveIntegerField(
        help_text="The expected length of the task in minutes"
    )
    grade_level = models.ForeignKey(
        "schools.GradeLevel",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        help_text="A grade level when a task is specific to a grade",
    )

    order_with_respect_to = "course"

    @classmethod
    def get_by_uuid(cls, user: User, uuid_str: str) -> Optional["CourseTask"]:
        """Get a task for a user by a uuid."""
        try:
            task_uuid = uuid.UUID(uuid_str)
        except ValueError:
            # A bad UUID should be ignored.
            return None
        grade_levels = GradeLevel.objects.filter(school_year__school__admin=user)
        return CourseTask.objects.filter(
            course__grade_levels__in=grade_levels, uuid=task_uuid
        ).first()

    def __str__(self):
        return self.description


class GradedWork(models.Model):
    """Any type of work that a student might be graded on like a test or quiz."""

    course_task = models.OneToOneField(
        "courses.CourseTask", on_delete=models.CASCADE, related_name="graded_work"
    )


class CourseResource(models.Model):
    """A resource related to a course (e.g., a book or workbook)"""

    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="resources"
    )
    uuid = models.UUIDField(default=uuid.uuid4, db_index=True)
    title = models.CharField(max_length=512)
    details = models.TextField(blank=True)

    def __str__(self):
        return self.title
