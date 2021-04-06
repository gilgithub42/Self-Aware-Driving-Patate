from multiprocessing import Process, shared_memory, Lock
import argparse
# from ddqn_II import run_ddqn, DQNAgent
from copy import deepcopy
from time import sleep
import sys
import pickle 

## This is ugly as fuck
memsize = 3880978

def run_agent(args, shm_name, lock):
    from ddqn_II import run_ddqn, DQNAgent
    agent = DQNAgent([80,80], 7, None, None, train=not args.test)
    weights = agent.model.get_weights()
    pkl = pickle.dumps(weights)
    shm.buf[:] = pkl
    run_ddqn(args, shm_name, lock)


if __name__ == "__main__":
    # Initialize the donkey environment
    # where env_name one of:
    env_list = [
        "donkey-warehouse-v0",
        "donkey-generated-roads-v0",
        "donkey-avc-sparkfun-v0",
        "donkey-generated-track-v0",
        "donkey-roboracingleague-track-v0",
        "donkey-waveshare-v0",
        "donkey-minimonaco-track-v0",
        "donkey-warren-track-v0"
    ]
    parser = argparse.ArgumentParser(description='ddqn')
    parser.add_argument('--sim', type=str, default="/home/yup/Desktop/Code/PATATE/DonkeySimLinux/donkey_sim.x86_64", help='path to unity simulator. maybe be left at manual if you would like to start the sim on your own.')
    parser.add_argument('--model', type=str, default="rl_driver.h5", help='path to model')
    parser.add_argument('--test', action="store_true", help='agent uses learned model to navigate env')
    parser.add_argument('--port', type=int, default=9091, help='port to use for websockets')
    parser.add_argument('--throttle', type=float, default=0.3, help='constant throttle for driving')
    parser.add_argument('--env_name', type=str, default="donkey-generated-roads-v0", help='name of donkey sim environment', choices=env_list)
    args = parser.parse_args()

    # agent = DQNAgent([80,80], 7, None, None, train=not args.test)
    # weights = agent.model.get_weights()
    # pkl = pickle.dumps(weights)
    shm = shared_memory.SharedMemory(create=True, size=memsize)
    lock = Lock()
    # print("len: LIKJAHNSDFLKJHASDLKJHASDLKJh", len(pkl))
    # print(type(weights), "\n", sys.getsizeof(weights))
    # shm.buf[:] = pkl
    # agent.target_model.set_weights(pickle.loads(shm.buf))
    # agent.shm = shm
    # agent.lock = lock

    # bytearray([x for x in weights])

    for i in range(1):
        p = Process(target = run_agent, args = (args, shm.name, lock))
        p.start()
        args = deepcopy(args)
        args.port += 1
        sleep(15)

    shm.close()
    shm.unlink()
    p.terminate()