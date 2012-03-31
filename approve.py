#!/usr/bin/python

import readline

from getpass import getuser

from qdb import Database

db = Database()
approver = getuser()

print "You are logged in as approver: {}".format(approver)

try:
    for q in db.unapproved():
        print "Candidate for approval #{id}, submitted {timestamp}\n\n{content}\n\n".format(**q),
        action = None
        while not action:
            action = raw_input("approve, delete, skip, quit? ").lower()
            if action.startswith("a"):
                db.approve(q['id'], approver)
            elif action.startswith("d"):
                db.delete(q['id'])
            elif action.startswith("s"):
                pass
            elif action.startswith("q"):
                raise EOFError
            else:
                action = None
    print "There are no more quotes to approve"
except (EOFError, KeyboardInterrupt):
    pass
