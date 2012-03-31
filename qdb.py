#!/usr/bin/python
#
# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# the accompanying COPYING file for more details.
#

import cherrypy
import datetime
import psycopg2

PG_CONNECTION=""

BASE_TEMPLATE=u"""<!DOCTYPE html>
<html>
<head>
<title>QDB: {title}</title>
<style>
body {{{{ width: 80%; margin: auto; font-family: monospace; }}}}
.noquotes {{{{ margin: auto; width: 15em; }}}}
.navigation {{{{ margin-bottom: 2em; }}}}
.navigation a {{{{ margin-right: 2em; }}}}
.quote {{{{ margin-bottom: 3em; }}}}
.submit {{{{ width: 100%; text-align: center; }}}}
</style>
</head>
<body>
<h1>Quote database</h1>
<div class="navigation"><a href="/submit">Submit your quote</a>
                        <a href="/">Latest</a>
                        <a href="/best">Best</a>
                        <a href="/random">Random</a>
</div>
{content}
</body>
</html>"""

INDEX_TEMPLATE=BASE_TEMPLATE.format(title=u"Index",
                                    content=\
u"""<div class="index">{quotes}</div>"""
                                    )

SUBMIT_TEMPLATE=BASE_TEMPLATE.format(title=u"Submit",
                                     content=\
u"""<div class="submit"><div class="message">{message}</div>
<form action="/submit" method="POST"><div class="form">
<p><textarea name="text" required="required" placeholder="Enter quote here" rows="10" cols="80"></textarea></p>
<p><input type="submit" /></p>
</form></div>"""
                                    )

NO_QUOTES=u"""<div class="noquotes">There are no quotes here</div>"""
SUBMITTED_MESSAGE=u"""<p>Your quote has been recorded and will be visible here: <a href="/{id}">{id}</a></p>"""

QUOTE=u"""<div class="quote" id="q{id}">
    <div class="qheader">
        <a href="/{id}" class="qlink">{id}</a>
        <a href="/rate/{id}/-1" class="minuslink">-</a>(<span class="rating">{rating}</span>)<a href="/rate/{id}/1" class="pluslink">+</a>
        <span class="timestamp">{timestamp}</span>
        <span class="approver">approved by {approver}</span>
    </div>
    <div class="qbody">{content}</div>
</div>"""

class Database(object):
    PERPAGE=50
    SCHEMA=(
            ("id", "SERIAL PRIMARY KEY"),
            ("content", "TEXT NOT NULL"),
            ("approver", "CHARACTER VARYING(8)"),
            ("rating", "INTEGER NOT NULL"),
            ("timestamp", "TIMESTAMP NOT NULL"),
            ("time_approved", "TIMESTAMP"),
            )

    def __init__(self, conn_string=PG_CONNECTION):
        self.connection = psycopg2.connect(conn_string)
        self.connection.autocommit = True

    def schema(self):
        cur = self.connection.cursor()
        cur.execute("""CREATE TABLE quote({});""".format(
                        ', '.join(" ".join(a) for a in self.SCHEMA))
                    )
        cur.close()

    def add(self, quote):
        cur = self.connection.cursor()
        cur.execute("""INSERT INTO quote(content, rating, timestamp)
                        VALUES (%s, %s, %s)
                        RETURNING id""",
                        (quote, 0, datetime.datetime.now()))
        ident = cur.fetchone()[0]
        cur.close()
        return ident

    def get(self, ident):
        cur = self.connection.cursor()
        cur.execute("""SELECT {}
                        FROM quote
                        WHERE id=%s AND approver IS NOT NULL""".format(
                            ', '.join(a[0] for a in self.SCHEMA)
                            ),
                        (ident,))
        data = cur.fetchone()
        cur.close()
        return dict(zip((a[0] for a in self.SCHEMA), data)) \
               if data else None

    def all(self, page=0, order='id DESC'):
        cur = self.connection.cursor()
        cur.execute("""SELECT {}
                        FROM quote
                        WHERE approver IS NOT NULL
                        ORDER BY {}
                        LIMIT {} OFFSET {}""".format(
                            ', '.join(a[0] for a in self.SCHEMA),
                            order,
                            self.PERPAGE,
                            page * self.PERPAGE))
        data = cur.fetchall()
        cur.close()
        return (dict(zip((a[0] for a in self.SCHEMA), q)) for q in data)

    def unapproved(self):
        cur = self.connection.cursor()
        cur.execute("""SELECT {}
                        FROM quote
                        WHERE approver IS NULL""".format(
                            ', '.join(a[0] for a in self.SCHEMA)))
        data = cur.fetchall()
        cur.close()
        return (dict(zip((a[0] for a in self.SCHEMA), q)) for q in data)

    def rate(self, quoteid, increment):
        cur = self.connection.cursor()
        cur.execute("""UPDATE quote SET rating = rating + %s WHERE id = %s""",
                    (increment, quoteid)
                    )
        cur.close()

    def delete(self, quoteid):
        cur = self.connection.cursor()
        cur.execute("""DELETE FROM quote WHERE id = %s""",
                    (quoteid,)
                    )
        cur.close()

    def approve(self, quoteid, approver):
        cur = self.connection.cursor()
        cur.execute("""UPDATE quote SET approver = %s, time_approved = NOW()  WHERE id = %s""",
                    (approver, quoteid)
                    )
        cur.close()

class Site(object):
    PERMITTED_ORDERS=("id DESC", "rating DESC", "RANDOM()")
    def __init__(self, *args, **kwargs):
        self.db = Database(*args, **kwargs)

    @cherrypy.expose
    def index(self, *args, **kwargs):
        quotes = None

        if args:
            try:
                quotes = self.db.get(int(args[0]))
                quotes = [quotes] if quotes else []
            except TypeError:
                pass

        order = kwargs.pop('order', '')
        if order not in self.PERMITTED_ORDERS:
            order = "id DESC"
        if quotes is None:
            quotes = self.db.all(order=order)

        quotes = ''.join(QUOTE.format(**q) for q in quotes) if quotes else None
        quotes = quotes or NO_QUOTES
        return INDEX_TEMPLATE.format(quotes=quotes)

    @cherrypy.expose
    def default(self, quoteid):
        return self.index(quoteid)

    @cherrypy.expose
    def rate(self, quoteid, value):
        self.db.rate(int(quoteid), 1 if int(value) > 0 else -1)
        return self.index(quoteid)

    @cherrypy.expose
    def best(self):
        return self.index(order='rating DESC')

    @cherrypy.expose
    def random(self):
        return self.index(order='RANDOM()')

    @cherrypy.expose
    def submit(self, **kwargs):
        text = kwargs.pop('text', None)

        if not text:
            return SUBMIT_TEMPLATE.format(message='')
        else:
            message = SUBMITTED_MESSAGE.format(id=self.db.add(text))
            return SUBMIT_TEMPLATE.format(message=message)

if __name__ == "__main__":
    import sys
    if sys.argv[0].startswith("qdb"):
        cherrypy.quickstart(Site())
