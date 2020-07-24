import argparse
import time
from concurrent import futures

import grpc
from pai.pouw.verification.verifier import verify_iteration
from pai.pouw.verification.verifier_pb2_grpc import VerifierServicer, add_VerifierServicer_to_server


class VerifierServicer(VerifierServicer):

    def Verify(self, request, context):
        return verify_iteration(request.msg_history_id,
                                request.msg_id,
                                request.nonce,
                                request.block_header,
                                redis_host=self.redis_host,
                                redis_port=self.redis_port
                                )


def main():
    parser = argparse.ArgumentParser(description='MXNet/Gluon MNIST Verifier')
    parser.add_argument('--redis-host', type=str, default='localhost',
                        help='redis host address used for worker synchronization')
    parser.add_argument('--redis-port', type=int, default=6379,
                        help='Redis port used for connecting to redis database')

    args = parser.parse_args()

    # create a gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    servicer = VerifierServicer()
    servicer.redis_host = args.redis_host
    servicer.redis_port = args.redis_port

    add_VerifierServicer_to_server(
        servicer, server)

    # listen on port 50011
    print('Starting server. Listening on port 50011.')
    server.add_insecure_port('[::]:50011')
    server.start()

    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    main()
