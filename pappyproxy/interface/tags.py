from ..console import CommandError
from ..util import confirm, load_reqlist

def tag_cmd(client, args):
    if len(args) == 0:
        raise CommandError("Usage: tag <tag> [reqid1] [reqid2] ...")
    if not args[0]:
        raise CommandError("Tag cannot be empty")
    tag = args[0]
    if len(args) == 1:
        reqids = '*'
    else:
        reqids = ','.join(args[1:])
    reqs = [r for r in load_reqlist(client, reqids, headers_only=True)]
    if len(reqs) > 10:
        cnt = confirm("You are about to tag {} requests with \"{}\". Continue?".format(len(reqs), tag))
        if not cnt:
            return
    for reqh in reqs:
        reqid = client.get_reqid(reqh)
        client.add_tag(reqid, tag)
            
def untag_cmd(client, args):
    if len(args) == 0:
        raise CommandError("Usage: untag <tag> [reqid1] [reqid2] ...")
    if not args[0]:
        raise CommandError("Tag cannot be empty")
    tag = args[0]
    if len(args) == 1:
        reqids = '*'
    else:
        reqids = ','.join(args[1:])
    reqs = [r for r in load_reqlist(client, reqids, headers_only=True)]
    if len(reqs) > 10:
        cnt = confirm("You are about to remove the \"{}\" tag from {} requests. Continue?".format(tag, len(reqs)))
        if not cnt:
            return
    for reqh in reqs:
        reqid = client.get_reqid(reqh)
        client.remove_tag(reqid, tag)

def clrtag_cmd(client, args):
    if len(args) == 0:
        raise CommandError("Usage: clrtag [reqid1] [reqid2] ...")
    reqids = []
    if len(args) == 1:
        reqids = '*'
    else:
        reqids = ','.join(args[1:])
    reqs = [r for r in load_reqlist(client, reqids, headers_only=True)]
    if len(reqs) > 5:
        cnt = confirm("You are about to clear ALL TAGS from {} requests. Continue?".format(len(reqs)))
        if not cnt:
            return
    for reqh in reqs:
        reqid = client.get_reqid(reqh)
        client.clear_tag(reqid)

def load_cmds(cmd):
    cmd.set_cmds({
        'clrtag': (clrtag_cmd, None),
        'untag': (untag_cmd, None),
        'tag': (tag_cmd, None),
    })
