# Copyright 2012-2014 Luke Dashjr
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the standard MIT license.  See COPYING for more details.

from binascii import b2a_hex as _b2a_hex
from hashlib import sha256 as _sha256
from struct import pack as _pack
from time import time as _time

import base58 as _base58
from pai.pouw.mining.blkmaker.extra import _Transaction, SIZEOF_WORKID, _request


def sha256_digest(data):
    return _sha256(data).digest()


def sha256_hexdigest(data):
    return _sha256(data).hexdigest()


def double_sha256(data):
    return _sha256(_sha256(data).digest()).digest()


def init_generation3(tmpl, script, override_cb=False):
    if (not tmpl.cbtxn is None) and not (override_cb and ('generate' in tmpl.mutations)):
        return (0, False)

    if len(script) >= 0xfd:
        return (0, True)

    sh = b''
    h = tmpl.height
    while h > 127:
        sh += _pack('<B', h & 0xff)
        h >>= 8
    sh += _pack('<B', h)
    sh = _pack('<B', len(sh)) + sh

    if getattr(tmpl, 'auxs', None):
        auxcat = b''
        for aux in tmpl.auxs.values():
            auxcat += aux
        if len(auxcat):
            sh += _pack('<B', len(auxcat)) + auxcat

    data = b''
    data += b"\x01\0\0\0"  # txn ver
    data += b"\x01"  # input count
    data += b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"  # prevout
    data += b"\xff\xff\xff\xff"  # index (-1)
    data += _pack('<B', len(sh))  # scriptSig length
    data += sh
    data += b"\xff\xff\xff\xff"  # sequence
    data += b"\x01"  # output count
    data += _pack('<Q', tmpl.cbvalue)
    data += _pack('<B', len(script))
    data += script
    data += b'\0\0\0\0'  # lock time

    txn = _Transaction(None)

    txn.data = data

    tmpl.cbtxn = txn

    tmpl.mutations.add('coinbase/append')
    tmpl.mutations.add('coinbase')
    tmpl.mutations.add('generate')

    return (tmpl.cbvalue, True)


init_generation2 = init_generation3


def init_generation(tmpl, script, override_cb=False):
    return init_generation2(tmpl, script, override_cb)[0]


def _hash_transactions(tmpl):
    for txn in tmpl.txns:
        if hasattr(txn, 'hash_'):
            continue
        txn.hash_ = double_sha256(txn.data)
    return True


def _build_merkle_branches(tmpl):
    if hasattr(tmpl, '_mrklbranch'):
        return True

    if not _hash_transactions(tmpl):
        return False

    branchcount = len(tmpl.txns).bit_length()
    branches = []

    merklehashes = [None] + [txn.hash_ for txn in tmpl.txns]
    while len(branches) < branchcount:
        branches.append(merklehashes[1])
        if len(merklehashes) % 2:
            merklehashes.append(merklehashes[-1])
        merklehashes = [None] + [double_sha256(merklehashes[i] + merklehashes[i + 1]) for i in
                                 range(2, len(merklehashes), 2)]

    tmpl._mrklbranch = branches

    return True


def _build_merkle_root(tmpl, coinbase):
    if not _build_merkle_branches(tmpl):
        return None

    lhs = double_sha256(coinbase)

    for rhs in tmpl._mrklbranch:
        lhs = double_sha256(lhs + rhs)

    return lhs


_cbScriptSigLen = 4 + 1 + 36


def _append_cb(tmpl, append, appended_at_offset=None):
    coinbase = tmpl.cbtxn.data
    # The following can be done better in both Python 2 and Python 3, but this way works with both
    origLen = ord(coinbase[_cbScriptSigLen:_cbScriptSigLen + 1])
    appendsz = len(append)

    if origLen > 100 - appendsz:
        return None

    cbExtraNonce = _cbScriptSigLen + 1 + origLen
    if not appended_at_offset is None:
        appended_at_offset[0] = cbExtraNonce

    newLen = origLen + appendsz
    coinbase = coinbase[:_cbScriptSigLen] + chr(newLen).encode('ascii') + coinbase[
                                                                          _cbScriptSigLen + 1:cbExtraNonce] + append + coinbase[
                                                                                                                       cbExtraNonce:]

    return coinbase


def append_coinbase_safe2(tmpl, append, extranoncesz=0, merkle_only=False):
    if 'coinbase/append' not in tmpl.mutations and 'coinbase' not in tmpl.mutations:
        raise RuntimeError('Coinbase appending not allowed by template')

    datasz = len(tmpl.cbtxn.data)
    if not merkle_only:
        if extranoncesz < SIZEOF_WORKID:
            extranoncesz = SIZEOF_WORKID
        elif extranoncesz == SIZEOF_WORKID:
            extranoncesz += 1
    availsz = 100 - extranoncesz - ord(tmpl.cbtxn.data[_cbScriptSigLen:_cbScriptSigLen + 1])
    if len(append) > availsz:
        return availsz

    newcb = _append_cb(tmpl, append)
    if newcb is None:
        raise RuntimeError('Append failed')

    return availsz


append_coinbase_safe = append_coinbase_safe2


def _extranonce(tmpl, workid):
    if not tmpl.cbtxn:
        return None

    coinbase = tmpl.cbtxn.data
    if not workid:
        return coinbase
    extradata = _pack('<Q', workid)
    coinbase = _append_cb(tmpl, extradata)
    return coinbase


def _set_times(tmpl, usetime=None, out_expire=None, can_roll_ntime=False):
    time_passed = int(usetime - tmpl._time_rcvd)
    timehdr = tmpl.curtime + time_passed
    if (timehdr > tmpl.maxtime):
        timehdr = tmpl.maxtime
    return _pack('<I', timehdr)
    if not out_expire is None:
        out_expire[0] = tmpl.expires - time_passed - 1

        if can_roll_ntime:
            # If the caller can roll the time header, we need to expire before reaching the maxtime
            maxtime_expire_limit = (tmpl.maxtime - timehdr) + 1
            if out_expire[0] > maxtime_expire_limit:
                out_expire[0] = maxtime_expire_limit


def _sample_data(tmpl, dataid):
    cbuf = _pack('<I', tmpl.version)
    cbuf += tmpl.prevblk

    cbtxndata = _extranonce(tmpl, dataid)
    if not cbtxndata:
        return None

    merkleroot = _build_merkle_root(tmpl, cbtxndata)
    if not merkleroot:
        return None
    cbuf += merkleroot

    cbuf += _pack('<I', tmpl.curtime)
    cbuf += tmpl.diffbits
    return cbuf


def get_data(tmpl, usetime=None, out_expire=None):
    if usetime is None: usetime = _time()
    if (not (time_left(tmpl, usetime) and work_left(tmpl))):
        return (None, None)

    dataid = tmpl.next_dataid
    tmpl.next_dataid += 1
    cbuf = _sample_data(tmpl, dataid)
    if cbuf is None:
        return (None, None)

    cbuf = cbuf[:68] + _set_times(tmpl, usetime, out_expire) + cbuf[68 + 4:]

    return (cbuf, dataid)


def get_mdata(tmpl, usetime=None, out_expire=None, extranoncesz=SIZEOF_WORKID, can_roll_ntime=True):
    if usetime is None: usetime = _time()
    if not (True
            and time_left(tmpl, usetime)
            and (not tmpl.cbtxn is None)
            and _build_merkle_branches(tmpl)
    ):
        return None

    if extranoncesz == SIZEOF_WORKID:
        # Avoid overlapping with blkmk_get_data use
        extranoncesz += 1

    cbuf = _pack('<I', tmpl.version)
    cbuf += tmpl.prevblk

    dummy = b'\0' * extranoncesz
    cbextranonceoffset = [None]
    cbtxn = _append_cb(tmpl, dummy, cbextranonceoffset)
    if cbtxn is None:
        return None
    cbuf += b'\0' * 0x20

    cbuf += _set_times(tmpl, usetime, out_expire, can_roll_ntime)
    cbuf += tmpl.diffbits

    return (cbuf, cbtxn, cbextranonceoffset[0], tmpl._mrklbranch)


def time_left(tmpl, nowtime=None):
    if nowtime is None: nowtime = _time()
    age = (nowtime - tmpl._time_rcvd)
    if age >= tmpl.expires:
        return 0
    return tmpl.expires - age


def work_left(tmpl):
    if not tmpl.version:
        return 0
    if 'coinbase/append' not in tmpl.mutations and 'coinbase' not in tmpl.mutations:
        return 1
    return 0xffffffffffffffff - tmpl.next_dataid


def _varintEncode(n):
    if n < 0xfd:
        return _pack('<B', n)
    # NOTE: Technically, there are more encodings for numbers bigger than
    # 16-bit, but transaction counts can't be that high with version 2 Bitcoin
    # blocks
    return b'\xfd' + _pack('<H', n)


def _assemble_submission(tmpl, data, dataid, nonce, foreign):
    data = data[:76]
    data += _pack('<I', nonce)

    if foreign or ('submit/truncate' not in tmpl.mutations or dataid):
        data += _varintEncode(1 + len(tmpl.txns))

        data += _extranonce(tmpl, dataid)

        if foreign or ('submit/coinbase' not in tmpl.mutations):
            for i in range(len(tmpl.txns)):
                data += tmpl.txns[i].data

    return _b2a_hex(data).decode('ascii')


def propose(tmpl, caps, foreign):
    jreq = _request(caps)
    jparams = jreq['params'][0]
    jparams['mode'] = 'proposal'
    if (not getattr(tmpl, 'workid', None) is None) and not foreign:
        jparams['workid'] = tmpl.workid

    dataid = 0
    if 'coinbase/append' in tmpl.mutations or 'coinbase' in tmpl.mutations:
        dataid = 1

    sdata = _sample_data(tmpl, dataid)
    blkhex = _assemble_submission(tmpl, sdata, dataid, 0, foreign)
    jparams['data'] = blkhex

    return jreq


def get_blkhex(tmpl, blkheader, dataid):
    data = blkheader
    data += _varintEncode(1 + len(tmpl.txns))
    data += _extranonce(tmpl, dataid)

    for i in range(len(tmpl.txns)):
        data += tmpl.txns[i].data

    return _b2a_hex(data).decode('ascii')


def submit(tmpl, data, dataid, nonce, foreign=False):
    blkhex = _assemble_submission(tmpl, data, dataid, nonce, foreign)

    info = {}
    if (not getattr(tmpl, 'workid', None) is None) and not foreign:
        info['workid'] = tmpl.workid

    return {
        'id': 0,
        'method': 'submitblock',
        'params': [
            blkhex,
            info
        ]
    }


def submit_foreign(tmpl, data, dataid, nonce):
    return submit(tmpl, data, dataid, nonce, True)


def address_to_script(addr):
    addrbin = _base58.b58decode(addr, 25)
    if addrbin is None:
        raise RuntimeError('Invalid address')
    addrver = _base58.get_bcaddress_version(addr)
    if addrver == 0 or addrver == 111:
        # Bitcoin pubkey hash or Testnet pubkey hash
        return b''
        + b'\x76'  # OP_DUP
        + b'\xa9'  # OP_HASH160
        + b'\x14'  # push 20 bytes
        + addrbin
        + b'\x88'  # OP_EQUALVERIFY
        + b'\xac'  # OP_CHECKSIG
    if addrver == 5 or addrver == 196:
        # Bitcoin script hash or Testnet script hash
        return b''
        + b'\xa9'  # OP_HASH160
        + b'\x14'  # push 20 bytes
        + addrbin
        + b'\x87'  # OP_EQUAL
    raise RuntimeError('Invalid address version')
