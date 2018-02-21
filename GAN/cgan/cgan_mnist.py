### -*- coding:utf-8 -*-

import keras
from keras.models import Sequential, Model
from keras.layers import Dense, Activation, Reshape, merge, Input
from keras.layers.normalization import BatchNormalization
from keras.layers.convolutional import UpSampling2D, Convolution2D

from keras.layers.advanced_activations import LeakyReLU
from keras.layers import Flatten, Dropout

import math
import numpy as np

import os
from keras.datasets import mnist
from keras.optimizers import Adam
from PIL import Image


WIDTH = 28
HEIGHT = 28
Z_DIM =30
CLASS_NUM = 10

BATCH_SIZE = 32
NUM_EPOCH = 50
GENERATED_IMAGE_PATH = '/volumes/data/dataset/gan/cgan_generated_images/' # 生成画像の保存先
#GENERATED_IMAGE_PATH = 'generated_images/' # 生成画像の保存先

def generator_model():
  model = Sequential()
  model.add(Dense(input_dim=(Z_DIM+CLASS_NUM), output_dim=1024)) # z=100, y=10
  model.add(BatchNormalization())
  model.add(Activation('relu'))
  model.add(Dense(128*7*7))
  model.add(BatchNormalization())
  model.add(Activation('relu'))
  model.add(Reshape((7,7,128), input_shape=(128*7*7,)))
  model.add(UpSampling2D((2,2)))
  model.add(Convolution2D(64,5,5,border_mode='same'))
  model.add(BatchNormalization())
  model.add(Activation('relu'))
  model.add(UpSampling2D((2,2)))
  model.add(Convolution2D(1,5,5,border_mode='same'))
  model.add(Activation('tanh'))
  return model

def discriminator_model():
  model = Sequential()
  model.add(Convolution2D(64,5,5,\
        subsample=(2,2),\
        border_mode='same',\
        input_shape=(WIDTH,HEIGHT,(1+CLASS_NUM))))
  model.add(LeakyReLU(0.2))
  model.add(Convolution2D(128,5,5,subsample=(2,2)))
  model.add(LeakyReLU(0.2))
  model.add(Flatten())
  model.add(Dense(256))
  model.add(LeakyReLU(0.2))
  model.add(Dropout(0.5))
  model.add(Dense(1))
  model.add(Activation('sigmoid'))
  return model

def generator_containing_discriminator(g,d):
  noise_input = Input(shape=(Z_DIM,))
  label_input = Input(shape=(CLASS_NUM,))
  label_10ch_input = Input(shape=(WIDTH,HEIGHT,CLASS_NUM,))
  input = merge([noise_input, label_input],mode='concat',concat_axis=-1)

  x_generator = g(input) # [batch, WIDTH, HEIGHT, channel=1]
  merged = merge([x_generator, label_10ch_input],mode='concat', concat_axis=3)
  d.trainable= False
  x_discriminator = d(merged)
  model = Model(input = [noise_input, label_input, label_10ch_input], output = x_discriminator)
  return model

def combine_images(generated_images):
  total = generated_images.shape[0]
  cols = int(math.sqrt(total))
  rows = math.ceil(float(total)/cols)
  WIDTH, HEIGHT = generated_images.shape[1:3]
  combined_image = np.zeros((HEIGHT*rows, WIDTH*cols),
              dtype=generated_images.dtype)

  for index, image in enumerate(generated_images):
    i = int(index/cols)
    j = index % cols
    combined_image[WIDTH*i:WIDTH*(i+1), HEIGHT*j:HEIGHT*(j+1)] = image[:, :,0]
  return combined_image

def label2images(label):
  images = np.zeros((WIDTH,HEIGHT,CLASS_NUM))
  images[:,:,label] += 1
  return images

def label2onehot(label):
  onehot = np.zeros(CLASS_NUM)
  onehot[label] = 1
  return onehot
def train():
  (X_train, y_train), (_, _) = mnist.load_data()
  X_train = (X_train.astype(np.float32) - 127.5)/127.5
  X_train = X_train.reshape(X_train.shape[0], X_train.shape[1], X_train.shape[2],1)

  discriminator = discriminator_model()
  d_opt = Adam(lr=1e-5, beta_1=0.1)
  discriminator.compile(loss='binary_crossentropy', optimizer=d_opt)

  # generator+discriminator （discriminator部分の重みは固定）
  discriminator.trainable = False
  generator = generator_model()
  dcgan = generator_containing_discriminator(generator, discriminator)

  g_opt = Adam(lr=.8e-4, beta_1=0.5)
  dcgan.compile(loss='binary_crossentropy', optimizer=g_opt)

  num_batches = int(X_train.shape[0] / BATCH_SIZE)
  print('Number of batches:', num_batches)
  for epoch in range(NUM_EPOCH):

    for index in range(num_batches):
      # generator用データ整形
      noise = np.array([np.random.uniform(-1, 1, Z_DIM) for _ in range(BATCH_SIZE)])
      randomLabel_batch = np.random.randint(0,CLASS_NUM,BATCH_SIZE) # label番号を生成する乱数,BATCH_SIZE長
      randomLabel_batch_onehot = np.array([label2onehot(i) for i in randomLabel_batch]) #shape[0]:batch, shape[1]:class
      noise_with_randomLabel = np.concatenate((noise, randomLabel_batch_onehot),axis=1) # zとyを結合
      generated_images = generator.predict(noise_with_randomLabel, verbose=0)
      randomLabel_batch_image = np.array([label2images(i) for i in randomLabel_batch]) # 生成データラベルの10ch画像
      generated_images_11ch = np.concatenate((generated_images, randomLabel_batch_image),axis=3)

      # discriminator用データ整形
      image_batch = X_train[index*BATCH_SIZE:(index+1)*BATCH_SIZE] # 実データの画像
      label_batch = y_train[index*BATCH_SIZE:(index+1)*BATCH_SIZE] # 実データのラベル
      label_batch_image = np.array([label2images(i) for i in label_batch]) # 実データラベルの10ch画像
      image_batch_11ch = np.concatenate((image_batch, label_batch_image),axis=3)

      ''' 
      # 生成画像を出力
      if index % 500 == 0:
        image = combine_images(generated_images)
        image = image*127.5 + 127.5
        if not os.path.exists(GENERATED_IMAGE_PATH):
          os.mkdir(GENERATED_IMAGE_PATH)
        Image.fromarray(image.astype(np.uint8))\
          .save(GENERATED_IMAGE_PATH+"%04d_%04d.png" % (epoch, index))
      '''
      # 生成画像を出力
      if index % 500 == 0:
        noise = np.array([np.random.uniform(-1, 1, Z_DIM) for _ in range(BATCH_SIZE)])
        randomLabel_batch = np.arange(BATCH_SIZE)%10  # label番号を生成する乱数,BATCH_SIZE長
        randomLabel_batch_onehot = np.array([label2onehot(i) for i in randomLabel_batch]) #shape[0]:batch, shape[1]:class
        noise_with_randomLabel = np.concatenate((noise, randomLabel_batch_onehot),axis=1) # zとyを結合
        generated_images = generator.predict(noise_with_randomLabel, verbose=0)
        image = combine_images(generated_images)
        image = image*127.5 + 127.5
        if not os.path.exists(GENERATED_IMAGE_PATH):
          os.mkdir(GENERATED_IMAGE_PATH)
        Image.fromarray(image.astype(np.uint8))\
          .save(GENERATED_IMAGE_PATH+"%04d_%04d.png" % (epoch, index))


      # discriminatorを更新
      X = np.concatenate((image_batch_11ch, generated_images_11ch))
      y = [1]*BATCH_SIZE + [0]*BATCH_SIZE
      d_loss = discriminator.train_on_batch(X, y)

      # generatorを更新
      noise = np.array([np.random.uniform(-1, 1, Z_DIM) for _ in range(BATCH_SIZE)])
      randomLabel_batch = np.random.randint(0,CLASS_NUM,BATCH_SIZE) # label番号を生成する乱数,BATCH_SIZE長
      randomLabel_batch_onehot = np.array([label2onehot(i) for i in randomLabel_batch]) #shape[0]:batch, shape[1]:class
      randomLabel_batch_image = np.array([label2images(i) for i in randomLabel_batch]) # 生成データラベルの10ch画像
      g_loss = dcgan.train_on_batch([noise, randomLabel_batch_onehot, randomLabel_batch_image], [1]*BATCH_SIZE)
      print("epoch: %d, batch: %d, g_loss: %f, d_loss: %f" % (epoch, index, g_loss, d_loss))

    generator.save_weights('generator.h5')
    discriminator.save_weights('discriminator.h5')

train()