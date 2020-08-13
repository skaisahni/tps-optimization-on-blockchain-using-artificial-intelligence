
#TPS Optimization on Blockchain using Artificial Intelligence#
* In this Project, we try to optimizate Tps of blockchain(Bitcoin core) using Deep learning(MXnet framework) by classify the work and disturbut work based 
  on node potential for that work to utilized the resources in the optimal way.
* Version==1.0.0
* Dependencies: Bitcin core; libboost; libevent;miniupnpc;libdb4.8;qt GUI;libqrencod;libzmq3;MxNet 
* you could clone bitcoin core from bitcoin github. 
#Elements of This project:
* paicoind is the bitcoin server binary
* verification/server.py is the PAICoin server extension that re-runs and verifies ML iterations when a lucky nonce is found by a miner
* worker.py contains the mining and training code executed by a miner; start_cluster.py is calling it to simulate several miners on the same machine
* client.py is the client code that triggers the training and mining processes.

