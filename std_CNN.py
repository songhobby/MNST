#!/usr/bin/env python3

import sys
import os
import time
import numpy as np
import theano
import theano.tensor as T
import lasagne
from six.moves import cPickle

#print images from numpy array
import matplotlib
import matplotlib.pyplot as plt

def display(input_array, filename, title, prediction):
	if not os.path.isdir('./Std/WrongTests'):
		os.mkdir('./Std/WrongTests')
	fig=plt.figure(1)
	ax=plt.subplot(111)
	plot=plt.imshow(input_array, cmap=matplotlib.cm.Greys)
	plt.title('actual: ' + title + '    predicted: '+prediction)
	fig.savefig('./Std/WrongTests/' + filename)

#Loading data from MNIST

import urllib.request
import gzip

def load_dataset():
	def download(filename, source='http://yann.lecun.com/exdb/mnist/'):
		print('Downloading {}'.format(filename))
		urllib.request.urlretrieve(source + filename, filename)

	def load_mnist_images(filename):
		if not os.path.exists(filename):
			download(filename)
		with gzip.open(filename, 'rb') as f:
			data = np.frombuffer(f.read(), np.uint8, offset=16)
		data = data.reshape(-1, 1, 28, 28)
#normalize the data
		return data / np.float32(256)

	def load_mnist_labels(filename):
		if not os.path.exists(filename):
			download(filename)
		with gzip.open(filename, 'rb') as f:
			data = np.frombuffer(f.read(), np.uint8, offset=8)
		return data

	X_train = load_mnist_images('train-images-idx3-ubyte.gz')
	y_train = load_mnist_labels('train-labels-idx1-ubyte.gz')
	X_test  = load_mnist_images('t10k-images-idx3-ubyte.gz')
	y_test  = load_mnist_labels('t10k-labels-idx1-ubyte.gz')

#Obtain the validation set
	X_train, X_val = X_train[:-1000],  X_train[-1000:]
	y_train, y_val = y_train[:-1000],  y_train[-1000:]

	return X_train, y_train, X_val, y_val, X_test, y_test

def build_cnn(input_var=None):
	network = lasagne.layers.InputLayer(shape=(None, 1, 28, 28), input_var=input_var)

	network = lasagne.layers.Conv2DLayer(
			network, num_filters=32, filter_size=(3,3),
			nonlinearity=lasagne.nonlinearities.rectify,
			W=lasagne.init.GlorotUniform())
	network = lasagne.layers.Conv2DLayer(
			network, num_filters=32, filter_size=(3,3),
			nonlinearity=lasagne.nonlinearities.rectify,
			W=lasagne.init.GlorotUniform())
	network = lasagne.layers.MaxPool2DLayer(network, pool_size=(2,2))
	network = lasagne.layers.Conv2DLayer(
			network, num_filters=64, filter_size=(3,3),
			nonlinearity=lasagne.nonlinearities.rectify,
			W=lasagne.init.GlorotUniform())
	network = lasagne.layers.Conv2DLayer(
			network, num_filters=64, filter_size=(3,3),
			nonlinearity=lasagne.nonlinearities.rectify,
			W=lasagne.init.GlorotUniform())
	network = lasagne.layers.MaxPool2DLayer(network, pool_size=(2,2))

	network = lasagne.layers.DropoutLayer(
			network, p=0.5)
	network = lasagne.layers.DenseLayer(
			network, num_units=200,
			nonlinearity=lasagne.nonlinearities.rectify)
	network = lasagne.layers.DropoutLayer(
			network, p=0.5)
	network = lasagne.layers.DenseLayer(
			network, num_units=200,
			nonlinearity=lasagne.nonlinearities.rectify)
	network = lasagne.layers.DropoutLayer(
			network, p=0.5)

	network = lasagne.layers.DenseLayer(
			network, num_units=10,
			nonlinearity=lasagne.nonlinearities.softmax)

	return network

#Batch generator
def gen_batches(inputs, targets, batchsize, shuffle=False):
	assert len(inputs) == len(targets)
	if shuffle:
		indices = np.arange(len(inputs))
		np.random.shuffle(indices)
	for start in range(0, len(inputs) - batchsize + 1, batchsize):
		if shuffle:
			excerpt = indices[start:start + batchsize]
		else:
			excerpt = slice(start, start + batchsize)
		yield inputs[excerpt], targets[excerpt]

#training
def main(num_epochs=50, save_num=0):
	#load the dataset
	print("Loading the dataset")
	X_train, y_train, X_val, y_val, X_test, y_test = load_dataset()
#define Theano variables
	input_var = T.tensor4('input_var')
	target_var = T.ivector('target_var')
#create CNN
	print("building the model")
	network = build_cnn(input_var)
#cost function 
	prediction = lasagne.layers.get_output(network)
	penalty = lasagne.regularization.regularize_layer_params(
			network, lasagne.regularization.l2)
	loss = lasagne.objectives.categorical_crossentropy(prediction, target_var)
	loss = loss.mean() + penalty*0.01
#training
	params = lasagne.layers.get_all_params(network, trainable=True)
	updates = lasagne.updates.nesterov_momentum(
			loss, params, learning_rate=0.1, momentum=0.5)
	#test_loss
	test_prediction = lasagne.layers.get_output(network, deterministic=True)
	test_loss_raw = lasagne.objectives.categorical_crossentropy(test_prediction, target_var)
	test_loss = test_loss_raw.mean()
	gradient = T.grad(test_loss, input_var)
	test_loss = test_loss + penalty*0.01
#test_loss
	test_acc = T.mean(T.eq(T.argmax(test_prediction, axis=1), target_var),
			dtype=theano.config.floatX)
	#complie functions
	train_fn = theano.function([input_var, target_var], loss, updates=updates)
	val_fn = theano.function([input_var, target_var], [test_loss, test_acc])
#helping test
	simple_prediction = theano.function([input_var], test_prediction)
#gradient
	gradient_f = theano.function([input_var, target_var], gradient)
	loss_f = theano.function([input_var, target_var], test_loss_raw)

	

	#Run the training
	print("Training starts")
	for epoch in range(num_epochs): #training
		train_err=0
		train_batches=0
		start_time=time.time()
		for batch in gen_batches(X_train, y_train, 128, shuffle=True):
			inputs, targets = batch
			train_err += train_fn(inputs, targets)
			train_batches += 1
#validation
		val_err = 0
		val_acc = 0
		val_batches = 0
		for batch in gen_batches(X_val, y_val, 128):
			inputs, targets = batch
			err, acc = val_fn(inputs, targets)
			val_err += err
			val_acc += acc
			val_batches += 1
#print the results
		print("Epoch {} of {} took {:.5f}s".format(
			epoch + 1, num_epochs, time.time() - start_time))
		print("    training loss:\t{:.10f}".format(train_err / train_batches))
		print("    validation loss:\t{:.10f}".format(val_err / val_batches))
		print("    validation accuracy:\t{:.5f} %".format(
			val_acc / val_batches * 100))


		#Test
	test_err = 0
	test_acc = 0
	test_batches = 0
	i = 0
	for batch in gen_batches(X_test, y_test, 128):
		inputs, targets = batch
		err, acc = val_fn(inputs, targets)
		test_err += err
		test_acc += acc
		test_batches += 1
		pre_list = simple_prediction(inputs)
		pre_list = np.argmax(pre_list, axis=1)
		err_indices = np.not_equal(pre_list, targets)
		if save_num:
			print("Saving the wrong pictures of batch", i)
			save_num -= 1
			for index, num in enumerate(err_indices):
				if num == 1:
					display(inputs[index][0], 
					'actual_' + str(targets[index]) + '_' + 
					'predict_' + str(pre_list[index]) + '_' +
					'_batch' + str(i) + '_' + str(index) + '.png', 
					str(targets[index]), str(pre_list[index]))
		i += 1


	print ("Tesing results:")
	print ("    test loss:\t\t{:.10f}".format(test_err / test_batches))
	print ("    test accuracy:\t{:.5f} %".format(
		test_acc / test_batches * 100))
	print ("Saving the network")
	f=open('./Std/std_f', 'wb')
	cPickle.dump(simple_prediction,f,cPickle.HIGHEST_PROTOCOL)
	f.close()
	f=open('./Std/std_grad_f', 'wb')
	cPickle.dump(gradient_f,f,cPickle.HIGHEST_PROTOCOL)
	f.close()
	f=open('./Std/std_loss_f', 'wb')
	cPickle.dump(loss_f,f,cPickle.HIGHEST_PROTOCOL)
	f.close()
	'''
	f=open('std_network.cnn', 'wb')
	cPickle.dump(network, f, cPickle.HIGHEST_PROTOCOL)
	f.close()
	f=open('std_network.var', 'wb')
	cPickle.dump(lasagne.layers.get_all_param_values(network), f, cPickle.HIGHEST_PROTOCOL)
	f.close()
	'''

if __name__ == '__main__':
	if not os.path.isdir('./Std'):
		os.mkdir('./Std')
	num_epochs = 50
	save_num = 0
	if len(sys.argv) > 1:
		num_epochs = int(sys.argv[1])
	if len(sys.argv) > 2:
		save_num = int(sys.argv[2])
	main(num_epochs, save_num)

