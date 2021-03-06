from __future__ import division


import time
import uuid
import itertools

from bitarray import bitarray


ENDIAN = 'big'
START_MARKER = bitarray('01001111' '01001000' '01000100', ENDIAN) #OHD
END_MARKER = bitarray('01000100' '01001000' '01001111', ENDIAN) #OHD


def to_stream(heartbeats):
    base_time = time.time()
    datagrams = []
    # Reverse iterate over the heartbeats for timestamp delta calculations
    for h in reversed(heartbeats):
        h = h.copy()
        prev_time = h['timestamp']
        h = _normalize_heartbeat(h, base_time)
        datagram = _to_datagram(h)
        datagrams.append(datagram)
        base_time = prev_time
    # Get back the original order
    datagrams.reverse()
    stream = bitarray()
    for d in datagrams:
        stream.extend(d)
    return stream


def from_stream(stream):
    heartbeats = []
    base_time = time.time()
    start_positions = stream.search(START_MARKER)
    end_positions = stream.search(END_MARKER)
    if len(start_positions) != len(end_positions):
        raise ValueError('Stream contains unmatched number of start and '
                         'end markers')

    # Reverse iterate over datagrams in stream because of timestamp deltas
    start_positions.reverse()
    end_positions.reverse()
    for start, end in itertools.izip(start_positions, end_positions):
        heartbeat = _from_datagram(stream[start:end])
        heartbeat = _denormalize_heartbeat(heartbeat, base_time)
        heartbeats.append(heartbeat)
        base_time = heartbeat['timestamp']
    # Get original order
    heartbeats.reverse()
    return heartbeats


def to_stream_str(heartbeats):
    return to_stream(heartbeats).tobytes()


def from_stream_str(stream):
    ba = bitarray()
    ba.frombytes(bytes(stream))
    return from_stream(ba)


def _normalize_heartbeat(heartbeat, base_time):
    # Get the device id as an int
    heartbeat['client_id'] = uuid.UUID(heartbeat['client_id'], version=4).int

    # Convert vendor id from hex string to int
    heartbeat['tuner_vendor'] = int(heartbeat['tuner_vendor'], 16)

    # Convert model id from hex string to int
    heartbeat['tuner_model'] = int(heartbeat['tuner_model'], 16)

    # Scale strength in the range of 0-10
    heartbeat['signal_strength'] = clamp_max(int(heartbeat['signal_strength'] / 10), 10)

    # Scale SNR to the range of 0-31
    heartbeat['snr'] = clamp_max(int(heartbeat['snr'] * 10), 31)

    # Convert bitrate to increments of 10 Kbps and clamp it to 63
    bitrate = int(heartbeat['bitrate'] / (1000 * 10))
    heartbeat['bitrate'] = clamp_max(bitrate, 63)

    # Calculate timestamp relative to the previous heartbeat's timestamp
    # and then reduce it to 5-second resolution
    timestamp = clamp_max(int((base_time - heartbeat['timestamp']) / 5), 127)
    heartbeat['timestamp'] = timestamp
    return heartbeat


def _denormalize_heartbeat(heartbeat, base_time):
    # Regain original timestamp (5-second resolution)
    heartbeat['timestamp'] = base_time - (heartbeat['timestamp'] * 5)

    # Convert id from int to hex
    heartbeat['tuner_vendor'] = id_hex(heartbeat['tuner_vendor'])

    # Convert id from int to hex
    heartbeat['tuner_model'] = id_hex(heartbeat['tuner_model'])

    # Regain original strength by scaling to 10
    heartbeat['signal_strength'] = heartbeat['signal_strength'] * 10

    # Downscale signal-noise ratio by 10 to original value
    heartbeat['snr'] = heartbeat['snr'] / 10

    # Rescale bitrate from increments of 10 Kbps to bps
    heartbeat['bitrate'] = int(heartbeat['bitrate'] * (1000 * 10))

    return heartbeat


def _from_datagram(datagram):
    heartbeat = dict()
    heartbeat['client_id'] = str(uuid.UUID(bytes=datagram[24:152].tobytes()))
    heartbeat['timestamp'] = from_bitarray(datagram[152:156])
    heartbeat['tuner_vendor'] = from_bitarray(datagram[156:172])
    heartbeat['tuner_model'] = from_bitarray(datagram[172:188])
    heartbeat['tuner_preset'] = from_bitarray(datagram[188:193])
    heartbeat['signal_lock'] = datagram[193]
    heartbeat['service_lock'] = datagram[194]
    heartbeat['signal_strength'] = from_bitarray(datagram[195:199])
    heartbeat['snr'] = from_bitarray(datagram[199:204])
    heartbeat['bitrate'] = from_bitarray(datagram[204:210])
    # Ignore 210-211 as padding
    count = from_bitarray(datagram[212:217])
    heartbeat['carousel_count'] = count
    heartbeat['carousel_status'] = datagram[217:217+count].tolist()
    return heartbeat


def _to_datagram(heartbeat):
    datagram = bitarray(34 * 8) # 272 bits
    datagram.setall(False)
    datagram[0:24] = START_MARKER
    datagram[24:152] = to_bitarray(heartbeat['client_id'], 16)
    datagram[152:156] = to_bitarray(heartbeat['timestamp'], 1)[4:]
    datagram[156:172] = to_bitarray(heartbeat['tuner_vendor'], 2)
    datagram[172:188] = to_bitarray(heartbeat['tuner_model'], 2)
    datagram[188:193] = to_bitarray(heartbeat['tuner_preset'], 1)[3:]
    datagram[193] = heartbeat['signal_lock']
    datagram[194] = heartbeat['service_lock']
    datagram[195:199] = to_bitarray(heartbeat['signal_strength'], 1)[4:]
    datagram[199:204] = to_bitarray(heartbeat['snr'], 1)[3:]
    datagram[204:210] = to_bitarray(heartbeat['bitrate'], 1)[2:]
    datagram[210:212] = False   # 2 bits of padding for later use
    datagram[212:217] = to_bitarray(heartbeat['carousel_count'], 1)[3:]
    datagram[217:248] = bitarray(heartbeat['carousel_status'])
    datagram[248:272] = END_MARKER
    return datagram


def clamp_max(val, maxval):
    return clamp(val, 0, maxval)


def clamp(val, minval, maxval):
    return max(minval, min(val, maxval))


def id_hex(id, length=4):
    return (hex(id)[2:]).zfill(length)


def to_bitarray(n, length):
    b = bitarray()
    b.frombytes(to_bytes(n, length))
    return b


def from_bitarray(b):
    while b.length() % 8 != 0:
        b.insert(0, False)
    return from_bytes(b.tobytes())


def to_bytes(n, length):
    h = '%x' % n
    s = ('0'*(len(h) % 2) + h).zfill(length*2).decode('hex')
    return s


def from_bytes(b):
    return int(b.encode('hex'), 16)
