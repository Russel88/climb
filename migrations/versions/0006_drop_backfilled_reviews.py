"""Drop the review markers 0005 back-filled onto every exercise

Revision ID: 0006_drop_backfilled_reviews
Revises: 0005_per_exercise_cycles
Create Date: 2026-09-14 00:00:00.000000

0005 turned every row of the old global ``personal_cycle_review`` into a review marker
on *every* progressive exercise. That assumed the old global cycle numbers and the new
per exercise ones count the same thing, and they do not: the global number came from a
calendar anchor, while a per exercise number is replayed from the cycle stamped on
``personal_set_log``. A single dismissal - the only thing that ever wrote a global review
row - therefore came back as "cycle N-1 already reviewed" for exercises that had never
finished a cycle at all, silently suppressing the first increase they actually earned.

Only the back-filled rows are removed. They are exactly the rows whose (cycle_number,
reviewed_at) pair still matches a row in ``personal_cycle_review``, which 0005 left in
place. Markers written by the per exercise flow carry their own ``reviewed_at`` default
and are untouched.
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_drop_backfilled_reviews"
down_revision = "0005_per_exercise_cycles"
branch_labels = None
depends_on = None


BACKFILLED_ROWS = """
    SELECT 1
    FROM personal_cycle_review pcr
    WHERE personal_exercise_cycle_review.cycle_number = pcr.cycle_number - 1
      AND personal_exercise_cycle_review.reviewed_at = pcr.reviewed_at
"""


def _has_legacy_table() -> bool:
    return sa.inspect(op.get_bind()).has_table("personal_cycle_review")


def upgrade() -> None:
    if not _has_legacy_table():
        return

    op.execute(f"DELETE FROM personal_exercise_cycle_review WHERE EXISTS ({BACKFILLED_ROWS})")


def downgrade() -> None:
    if not _has_legacy_table():
        return

    op.execute(
        """
        INSERT INTO personal_exercise_cycle_review (exercise_id, cycle_number, reviewed_at)
        SELECT pe.id, pcr.cycle_number - 1, pcr.reviewed_at
        FROM personal_exercise pe
        CROSS JOIN personal_cycle_review pcr
        WHERE pe.kind::text = 'progressive'
          AND pcr.cycle_number > 1
        ON CONFLICT (exercise_id, cycle_number) DO NOTHING
        """
    )
