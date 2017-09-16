"""
Add 
"""

from yoyo import step

__depends__ = {'20170913_01_u4eZj-create-initial-schema'}

steps = [
    step("""
        ALTER TABLE transactions ADD COLUMN marked INT DEFAULT 0
    """,
    """
        ALTER TABLE transactions DROP COLUMN marked
    """)
]
