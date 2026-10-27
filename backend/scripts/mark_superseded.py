"""Đánh dấu BLLĐ 2012 hết hiệu lực khi BLLĐ 2019 có hiệu lực (2021-01-01)."""

from sqlalchemy import text

from app.db.base import engine

with engine.begin() as c:
    n = c.execute(
        text(
            "UPDATE legal_node SET effective_to='2021-01-01' "
            "WHERE doc_id='blld2012' AND effective_to IS NULL"
        )
    ).rowcount
    c.execute(
        text(
            "UPDATE legal_document SET expired_date='2021-01-01', status='expired' "
            "WHERE doc_id='blld2012'"
        )
    )
    print("blld2012 nodes marked expired:", n)
