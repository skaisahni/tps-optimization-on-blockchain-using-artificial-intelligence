# Copyright 2012-2014 Luke Dashjr
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the standard MIT license.  See COPYING for more details.

from time import time as _time

from pai.pouw.mining.blkmaker.extra import _Transaction, _a2b_hex, _request, SIZEOF_WORKID

from . import blkmaker as _blkmaker


class _LPInfo:
    pass


class Template:
    def __init__(self):
        self.auxs = {}
        self.sigoplimit = 0xffff
        self.sizelimit = 0xffffffff
        self.maxtime = 0xffffffff
        self.maxtimeoff = 0x7fff
        self.mintime = 0
        self.mintimeoff = -0x7fff
        self.maxnonce = 0xffffffff
        self.expires = 0x7fff
        self.cbtxn = None
        self.next_dataid = 0
        self.version = None

    def addcaps(self):
        # TODO: make this a lot more flexible for merging
        # For now, it's a simple "filled" vs "not filled"
        if self.version:
            return 0
        return ('coinbasetxn', 'workid', 'time/increment', 'coinbase/append', 'version/force', 'version/reduce',
                'submit/coinbase', 'submit/truncate')

    def get_longpoll(self):
        return self.lp

    def get_submitold(self):
        return self.submitold

    # Wrappers around blkmaker, for OO friendliness
    def init_generation3(self, script, override_cb=False):
        return _blkmaker.init_generation3(self, script, override_cb)

    def init_generation2(self, script, override_cb=False):
        return _blkmaker.init_generation2(self, script, override_cb)

    def init_generation(self, script, override_cb=False):
        return _blkmaker.init_generation(self, script, override_cb)

    def append_coinbase_safe2(self, append, extranoncesz=0, merkle_only=False):
        return _blkmaker.append_coinbase_safe2(self, append, extranoncesz, merkle_only)

    def append_coinbase_safe(self, append, extranoncesz=0, merkle_only=False):
        return _blkmaker.append_coinbase_safe(self, append, extranoncesz, merkle_only)

    def get_data(self, usetime=None):
        return _blkmaker.get_data(self, usetime)

    def get_mdata(self, usetime=None, out_expire=None, extranoncesz=SIZEOF_WORKID):
        return _blkmaker.get_mdata(self, usetime, out_expire, extranoncesz)

    def time_left(self, nowtime=None):
        return _blkmaker.time_left(self, nowtime)

    def work_left(self):
        return _blkmaker.work_left(self)

    def propose(self, caps, foreign):
        return _blkmaker.propose(self, caps, foreign)

    def submit(self, data, dataid, nonce, foreign=False):
        return _blkmaker.submit(self, data, dataid, nonce, foreign)

    def submit_foreign(self, data, dataid, nonce):
        return _blkmaker.submit_foreign(self, data, dataid, nonce)

    # JSON-specific stuff
    def request(self, address=None, lpid=None):
        return _request(self.addcaps(), address, lpid)

    def add(self, json, time_rcvd=None):
        if time_rcvd is None: time_rcvd = _time()
        if self.version:
            return False

        if 'result' in json:
            if json.get('error', None):
                raise ValueError('JSON result is error')
            json = json['result']

        self.diffbits = _a2b_hex(json['bits'])[::-1]
        self.curtime = json['curtime']
        self.height = json['height']
        self.prevblk = _a2b_hex(json['previousblockhash'])[::-1]
        self.sigoplimit = json.get('sigoplimit', self.sigoplimit)
        self.sizelimit = json.get('sizelimit', self.sizelimit)
        self.version = json['version']

        self.cbvalue = json.get('coinbasevalue', None)
        self.workid = json.get('workid', None)

        self.expires = json.get('expires', self.expires)
        self.maxtime = json.get('maxtime', self.maxtime)
        self.maxtimeoff = json.get('maxtimeoff', self.maxtimeoff)
        self.mintime = json.get('mintime', self.mintime)
        self.mintimeoff = json.get('mintimeoff', self.mintimeoff)

        self.lp = _LPInfo()
        if 'longpollid' in json:
            self.lp.lpid = json['longpollid']
            self.lp.uri = json.get('longpolluri', None)
        self.submitold = json.get('submitold', True)

        self.txns = [_Transaction(t) for t in json['transactions']]

        if 'coinbasetxn' in json:
            self.cbtxn = _Transaction(json['coinbasetxn'])

        if 'coinbaseaux' in json:
            for aux in json['coinbaseaux']:
                self.auxs[aux] = _a2b_hex(json['coinbaseaux'][aux])

        if 'target' in json:
            self.target = _a2b_hex(json['target'])

        self.mutations = set(json.get('mutable', ()))

        if (self.version > 2 or (self.version == 2 and not self.height)):
            if 'version/reduce' in self.mutations:
                self.version = 2 if self.height else 1
            elif 'version/force' not in self.mutations:
                raise ValueError("Unrecognized block version, and not allowed to reduce or force it")

        self._time_rcvd = time_rcvd;

        return True

    def get_blkhex(self, blkheader, dataid):
        return _blkmaker.get_blkhex(self, blkheader, dataid)
