'''
file: ddqn.py
author: Felix Yu
date: 2018-09-12
original: https://github.com/flyyufelix/donkey_rl/blob/master/donkey_rl/src/ddqn.py
'''
import os
import sys
import random
import argparse
import signal
import uuid
import numpy as np
import gym
import cv2
import skimage as skimage
from skimage import transform, color, exposure
from skimage.transform import rotate
from skimage.viewer import ImageViewer
from collections import deque

import gym_donkeycar
import pickle

from multiprocessing import Process, shared_memory, Lock

from config import cte_config

from tensorflow.keras.layers import Dense
from tensorflow.keras.optimizers import Adam, Adagrad
from tensorflow.keras.models import Sequential
# from tensorflow.keras.initializers import normal, identity
from tensorflow.keras.initializers import identity
from tensorflow.keras.models import model_from_json
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Activation, Flatten
from tensorflow.keras.layers import Conv2D, MaxPooling2D
import tensorflow as tf
# from tensorflow.keras import backend as K
from tensorflow.compat.v1.keras import backend as K

EPISODES = 20000
img_rows, img_cols = 80, 80
# Convert image into Black and white

turn_bins = 7
img_channels = 4 # We stack 4 frames

class DQNAgent:
    def __init__(self, state_size, action_space, shm, lock, train=True):
        self.t = 0
        self.max_Q = 0
        self.train = train
        # Get size of state and action
        self.state_size = state_size
        self.action_space = action_space
        self.action_size = action_space
        # These are hyper parameters for the DQN
        self.discount_factor = 0.99
        self.learning_rate = 1e-4
        if (self.train):
            self.epsilon = 0.9
            self.initial_epsilon = 0.9
        else:
            self.epsilon = 1e-6
            self.initial_epsilon = 1e-6
        self.epsilon_min = 0.02
        self.batch_size = 64
        self.train_start = 100
        self.explore = 10000
        # Create replay memory using deque
        self.memory = deque(maxlen=10000)
        # Create main model and target model
        self.model = self.build_model()
        self.target_model = self.build_model(trainable=False)
        self.update_target_model()
        # Copy the model to target model
        # --> initialize the target model so that the parameters of model & target model to be same
        if (shm is not None):
            self.model.set_weights(pickle.loads(shm.buf))
            self.target_model.set_weights(pickle.loads(shm.buf))
        self.shm = shm
        self.lock = lock

    def build_model(self, trainable = True):
        model = Sequential()
        model.add(Conv2D(24, (5, 5), strides=(2, 2), padding="same",input_shape=(img_rows,img_cols,img_channels), trainable=trainable))  #80*80*4
        model.add(Activation('relu'))
        model.add(Conv2D(32, (5, 5), strides=(2, 2), padding="same", trainable=trainable))
        model.add(Activation('relu'))
        model.add(Conv2D(64, (5, 5), strides=(2, 2), padding="same", trainable=trainable))
        model.add(Activation('relu'))
        model.add(Conv2D(64, (3, 3), strides=(2, 2), padding="same", trainable=trainable))
        model.add(Activation('relu'))
        model.add(Conv2D(64, (3, 3), strides=(1, 1), padding="same", trainable=trainable))
        model.add(Activation('relu'))
        model.add(Flatten())
        model.add(Dense(512, trainable=trainable))
        model.add(Activation('relu'))
        # 15 categorical bins for Steering angles
        model.add(Dense(turn_bins, activation="linear", trainable=trainable)) 
        # adagrad = Adagrad(lr=self.learning_rate)
        model.compile(loss='mse', optimizer='SGD')
        return model


    def rgb2gray(self, rgb):
        '''
        take a numpy rgb image return a new single channel image converted to greyscale
        '''
        return np.dot(rgb[...,:3], [0.299, 0.587, 0.114])


    def process_image(self, obs):
        obs = self.rgb2gray(obs)
        obs = cv2.resize(obs, (img_rows, img_cols))
        return obs


    def update_target_model(self):
        self.target_model.set_weights(self.model.get_weights())
    # Get action from model using epsilon-greedy policy


    def get_action(self, s_t):
        if np.random.rand() <= self.epsilon:
            return self.action_space.sample()[0]       
        else:
            #print("Return Max Q Prediction")
            q_value = self.model.predict(s_t)
            # Convert q array to steering value
            return linear_unbin(q_value[0])


    def replay_memory(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))


    def update_epsilon(self):
        if self.epsilon > self.epsilon_min:
            self.epsilon -= (self.initial_epsilon - self.epsilon_min) / self.explore


    def train_replay(self):
        if len(self.memory) < self.train_start:
            return
        batch_size = min(self.batch_size, len(self.memory))
        minibatch = random.sample(self.memory, batch_size)
        state_t, action_t, reward_t, state_t1, terminal = zip(*minibatch)
        state_t = np.concatenate(state_t)
        state_t1 = np.concatenate(state_t1)
        targets = self.model.predict(state_t)
        self.max_Q = np.max(targets[0])
        target_val = self.model.predict(state_t1)
        target_val_ = self.target_model.predict(state_t1)
        for i in range(batch_size):
            if terminal[i]:
                targets[i][action_t[i]] = reward_t[i]
            else:
                a = np.argmax(target_val[i])
                targets[i][action_t[i]] = reward_t[i] + self.discount_factor * (target_val_[i][a])
        self.model.train_on_batch(state_t, targets)


    def load_model(self, name):
        self.model.load_weights(name)


    # Save the model which is under training
    def save_model(self, name):
        self.model.save_weights(name)

## Utils Functions ##
def linear_bin(a):
    """
    Convert a value to a categorical array.
    Parameters
    ----------
    a : int or float
        A value between -1 and 1
    Returns
    -------
    list of int
        A list of length 15 with one item set to 1, which represents the linear value, and all other items set to 0.
    """
    a = a + 1
    b = round(a / (2 / (turn_bins - 1)))
    arr = np.zeros(turn_bins)
    arr[int(b)] = 1
    # print("bin", a, arr)
    return arr

def linear_unbin(arr):
    """
    Convert a categorical array to value.
    See Also
    --------
    linear_bin
    """
    if not len(arr) == turn_bins:
        raise ValueError('Illegal array length, must be 15')
    b = np.argmax(arr)
    a = b * (2 / (turn_bins - 1)) - 1
    # print("unbin", a, b)
    return a

def run_ddqn(args, shm_name, lock):
    '''
    run a DDQN training session, or test its result, with the donkey simulator
    '''
    # only needed if TF==1.13.1
    shm = shared_memory.SharedMemory(name = shm_name)


    config = tf.compat.v1.ConfigProto(log_device_placement=True)
    config.gpu_options.allow_growth = True
    print(config)
    sess = tf.compat.v1.Session(config=config)
    K.set_session(sess)
    conf = {"exe_path" : args.sim, 
        "host" : "127.0.0.1",
        "port" : args.port,
        "body_style" : "donkey",
        "body_rgb" : (128, 128, 128),
        "car_name" : "me",
        "font_size" : 100,
        "racer_name" : "DDQN",
        "country" : "FR",
        "bio" : "Learning to drive w DDQN RL",
        "guid" : str(uuid.uuid4()),
        "max_cte" : 7,
        }
    # Construct gym environment. Starts the simulator if path is given.
    env = gym.make(args.env_name, conf=conf)
    # not working on windows...
    def signal_handler(signal, frame):
        print("catching ctrl+c")
        env.unwrapped.close()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGABRT, signal_handler)
    # Get size of state and action from environment
    state_size = (img_rows, img_cols, img_channels)
    action_space = env.action_space # Steering and Throttle
    try:

        agent = DQNAgent(state_size, action_space, shm, lock, train=not args.test)
        throttle = args.throttle # Set throttle as constant value
        episodes = []
        if os.path.exists(args.model):
            print("load the saved model")
            agent.load_model(args.model)
        for e in range(EPISODES):
            print("Episode: ", e)
            done = False
            obs = env.reset()
            episode_len = 0
            x_t = agent.process_image(obs)
            s_t = np.stack((x_t,x_t,x_t,x_t),axis=2)
            # In Keras, need to reshape
            s_t = s_t.reshape(1, s_t.shape[0], s_t.shape[1], s_t.shape[2]) #1*80*80*4       
            while not done:
                # Get action for the current state and go one step in environment
                steering = agent.get_action(s_t)
                action = [steering, throttle]
                next_obs, reward, done, info = env.step(action)
                cte = env.viewer.handler.cte
                cte_corrected = cte + cte_config.cte_offset
                # print("speed : ", env.viewer.handler.speed)
                done = cte_config.done_func(cte_corrected)
                #if (env.viewer.handler.cte > 7 + 355):
                #    done = True
                if (done):
                    reward = -100
                reward = reward + conf["max_cte"] - abs(cte_corrected)
                #  + speed_reward(env.viewer.handler.speed)
                # print(env.viewer.handler.speed, reward)
                x_t1 = agent.process_image(next_obs)
                x_t1 = x_t1.reshape(1, x_t1.shape[0], x_t1.shape[1], 1) #1x80x80x1
                s_t1 = np.append(x_t1, s_t[:, :, :, :3], axis=3) #1x80x80x4
                # Save the sample <s, a, r, s'> to the replay memory
                agent.replay_memory(s_t, np.argmax(linear_bin(steering)), reward, s_t1, done)
                agent.update_epsilon()
                if agent.train:
                    agent.train_replay()
                s_t = s_t1
                agent.t = agent.t + 1
                episode_len = episode_len + 1
                if agent.t % 30 == 0:
                    print("EPISODE",  e, "TIMESTEP", agent.t,"/ ACTION", action, "/ REWARD", reward, "/ EPISODE LENGTH", episode_len, "/ Q_MAX " , agent.max_Q)
                if done:
                    # Every episode update the target model to be same with model
                    agent.update_target_model()
                    episodes.append(e)
                    # Save model for each episode
                    if agent.train:
                        agent.save_model(args.model)
                    print("episode:", e, "  memory length:", len(agent.memory),
                        "  epsilon:", agent.epsilon, " episode length:", episode_len)
    except Exception as e:
        print(f"{e}\nstopping run...")
    finally:
        env.unwrapped.close()

