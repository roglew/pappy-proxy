
def test_cmd(client, args):
    print("args:", ', '.join(args))
    print("ping:", client.ping())

def load_cmds(cons):
    cons.set_cmd("test", test_cmd)
