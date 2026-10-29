"""Report queries limited to what the signed-in user may see."""
import auth


def my_reports(conn, user):
    where, params = auth.scope_sql(user)
    return [dict(x) for x in conn.execute("SELECT * FROM reports WHERE " + where + " ORDER BY id DESC", params).fetchall()]
