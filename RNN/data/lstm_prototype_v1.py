# definition vanilla LSTM network233

# import relevant libraries
import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib
import numpy as np
import trajectories
import loader
import argparse
import gc
import logging
import os
import sys
import time
import matplotlib.pyplot as plt 

# build argparser
parser = argparse.ArgumentParser()

parser.add_argument('--input_size', type=int, default=2)
parser.add_argument('--output_size', type=int, default=5)
# RNN size parameter (dimension of the output/hidden state)
parser.add_argument('--rnn_size', type=int, default=128,
                 help='size of RNN hidden state')
# Size of each batch parameter
parser.add_argument('--batch_size', type=int, default=10,
                 help='minibatch size')
# Length of sequence to be considered parameter
parser.add_argument('--seq_length', type=int, default=20,
                 help='RNN sequence length')
parser.add_argument('--pred_length', type=int, default=12,
                 help='prediction length')
# Number of epochs parameter
parser.add_argument('--num_epochs', type=int, default=30,
                 help='number of epochs')
# Frequency at which the model should be saved parameter
parser.add_argument('--save_every', type=int, default=400,
                 help='save frequency')
# TODO: (resolve) Clipping gradients for now. No idea whether we should
# Gradient value at which it should be clipped
parser.add_argument('--grad_clip', type=float, default=10.,
                 help='clip gradients at this value')
# Learning rate parameter
parser.add_argument('--learning_rate', type=float, default=0.003,
                 help='learning rate')
# Decay rate for the learning rate parameter
parser.add_argument('--decay_rate', type=float, default=0.95,
                 help='decay rate for rmsprop')
# Dropout not implemented.
# Dropout probability parameter
parser.add_argument('--dropout', type=float, default=0.5,
                 help='dropout probability')
# Dimension of the embeddings parameter
parser.add_argument('--embedding_size', type=int, default=64,
                 help='Embedding dimension for the spatial coordinates')
# Size of neighborhood to be considered parameter
parser.add_argument('--neighborhood_size', type=int, default=32,
                 help='Neighborhood size to be considered for social grid')
# Size of the social grid parameter
parser.add_argument('--grid_size', type=int, default=4,
                 help='Grid size of the social grid')
# Maximum number of pedestrians to be considered
parser.add_argument('--maxNumPeds', type=int, default=27,
                 help='Maximum Number of Pedestrians')

# Lambda regularization parameter (L2)
parser.add_argument('--lambda_param', type=float, default=0.0005,
                 help='L2 regularization parameter')
# Cuda parameter
parser.add_argument('--use_cuda', action="store_true", default=False,
                 help='Use GPU or not')
# GRU parameter
parser.add_argument('--gru', action="store_true", default=False,
                 help='True : GRU cell, False: LSTM cell')
# drive option
parser.add_argument('--drive', action="store_true", default=False,
                 help='Use Google drive or not')
# number of validation will be used
parser.add_argument('--num_validation', type=int, default=2,
                 help='Total number of validation dataset for validate accuracy')
# frequency of validation
parser.add_argument('--freq_validation', type=int, default=1,
                 help='Frequency number(epoch) of validation using validation data')
# frequency of optimizer learning decay
parser.add_argument('--freq_optimizer', type=int, default=8,
                 help='Frequency number(epoch) of learning decay for optimizer')
# store grids in epoch 0 and use further.2 times faster -> Intensive memory use around 12 GB
parser.add_argument('--grid', action="store_true", default=True,
                 help='Whether store grids and use further epoch')

# Dataset options
parser.add_argument('--dataset_name', default='zara1', type=str)
parser.add_argument('--delim', default='\t')
parser.add_argument('--loader_num_workers', default=4, type=int)
parser.add_argument('--obs_len', default=8, type=int)
parser.add_argument('--pred_len', default=12, type=int)
parser.add_argument('--skip', default=1, type=int)

args = parser.parse_args()

data_dir = "/home/roongtaaahsih/ped_traj/sgan_ab/scripts/datasets/eth/train"


""" Class for defining the Vanilla LSTM Network """
class VanillaLSTMNet(nn.Module):
    def __init__(self):
        """" Initialize the network here. You can use a combination of nn.LSTMCell and nn.Linear. 
        Number of layers and hidden size is up to you. Hint: A network with less than 3 layers and 
        64 dimensionality should suffice.
        """
        super(VanillaLSTMNet, self).__init__()
        
        # Inputs to the LSTMCell's are (input, (h_0, c_0)):
        # 1. input of shape (batch, input_size): tensor containing input 
        # features
        # 2a. h_0 of shape (batch, hidden_size): tensor containing the 
        # initial hidden state for each element in the batch.
        # 2b. c_0 of shape (batch, hidden_size): tensor containing the 
        # initial cell state for each element in the batch.
        
        # Outputs: h_1, c_1
        # 1. h_1 of shape (batch, hidden_size): tensor containing the next 
        # hidden state for each element in the batch
        # 2. c_1 of shape (batch, hidden_size): tensor containing the next 
        # cell state for each element in the batch
        
        # set parameters for network architecture
        self.embedding_size = 64
        self.input_size = 2
        self.output_size = 2
        self.dropout_prob = 0.5 
        
        # linear layer to embed the input position
        self.input_embedding_layer = nn.Linear(self.input_size, self.embedding_size)
        
        # define lstm cell
        self.lstm_cell = nn.LSTMCell(self.embedding_size, self.embedding_size)

        # linear layer to map the hidden state of LSTM to output
        self.output_layer = nn.Linear(self.embedding_size, self.output_size)
        
        # ReLU and dropout unit
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(self.dropout_prob)
        
        pass
 
    def forward(self, observed_batch, pred_len = 0):
        """ This function takes the input sequence and predicts the output sequence. 
        
            args:
                observed_seq (torch.Tensor) : Input sequence with shape <batch size x sequence length x number of dimensions>
                pred_len (int) : Length of the sequence to be predicted.

        """
        
        '''
        Forward pass for the model.
        '''
        
        output_seq = []

        ht = torch.zeros(observed_batch.size(1), self.embedding_size, dtype=torch.float)
        ct = torch.zeros(observed_batch.size(1), self.embedding_size, dtype=torch.float)

        seq, peds, coords = observed_batch.shape
        #Feeding the observed trajectory to the network
        for step in range(seq):
            observed_step = observed_batch[step, :, :]
            lin_out = self.input_embedding_layer(observed_step.view(peds,2))
            ht, ct = self.lstm_cell(lin_out, (ht, ct))
            out = self.output_layer(self.dropout(ht))

        print("out's shape:", out.shape)
        #Getting the predicted trajectory from the pedestrian 
        for i in range(pred_len):
            lin_out = self.input_embedding_layer(out)
            ht, ct = self.lstm_cell(lin_out, (ht,ct))
            out = self.output_layer(self.dropout(ht))
            output_seq += [out]

        output_seq = torch.stack(output_seq).squeeze() # convert list to tensor
        return output_seq

# Defining test function to return avg test loss for each epoch
def test(vanilla_lstm_net,args):
    test_data_dir = "/home/roongtaaahsih/ped_traj/sgan_ab/scripts/datasets/eth/test"

    # retrieve dataloader
    dataset, dataloader = loader.data_loader(args, test_data_dir)

    # define parameters for training and testing loops
    pred_len = 12
    criterion = nn.MSELoss() # MSE works best for difference between predicted and actual coordinate paths

    # initialize lists for capturing losses
    test_loss = []

    # now, test the model
    for i, batch in enumerate(dataloader):
      test_observed_batch = batch[0]
      test_target_batch = batch[1]
      out = vanilla_lstm_net(test_observed_batch, pred_len=pred_len) # forward pass of lstm network for training
      print("out's shape:", out.shape)
      cur_test_loss = criterion(out, test_target_batch) # calculate MSE loss
      print('Current test loss: {}'.format(cur_test_loss.item())) # print current test loss
      test_loss.append(cur_test_loss.item())
    avg_testloss = sum(test_loss)/len(test_loss)
    print("============= Average test loss:", avg_testloss, "====================")

    return avg_testloss

def main(args):
    
    # define parameters for training and testing loops
    num_epoch = 5
    # pred_freq = 1
    pred_len = 12
    learning_rate = 0.0005
    
    # get data
    # train_input, train_target, test_input, test_target = getData()
    dataset, dataloader = loader.data_loader(args, data_dir)

    # define the network and criterion
    vanilla_lstm_net = VanillaLSTMNet()
    # vanilla_lstm_net.double() # casts tensor to double
    criterion = nn.MSELoss() # MSE works best for difference between predicted and actual coordinate paths
    # define the optimizer
    optimizer = optim.Adam(vanilla_lstm_net.parameters(), lr=learning_rate)

    # initialize lists for capturing losses
    train_loss = []
    test_loss = []
    avg_train_loss = []
    avg_test_loss = []
    train_avgD_error=[]
    train_finalD_error=[]
    avg_train_avgD_error=[]
    avg_train_finalD_error=[]
    test_finalD_error=[]
    tets_avgD_error=[]
    std_train_loss = []
    std_test_loss = []

    '''train for 'num_epoch' epochs and test every 'pred_freq' epochs & when predicting use pred_len=6'''
    
    ### TRAINING FUNCTION ###
    for i in range(num_epoch):
        print('======================= Epoch: {cur_epoch} / {total_epochs} ======================='.format(cur_epoch=i, total_epochs=num_epoch))
        def closure():
            for i, batch in enumerate(dataloader):
                # print("batch length:", len(batch)) # DEBUG
                train_batch = batch[0]
                target_batch = batch[1]
                print("train_batch's shape", train_batch.shape)
                print("target_batch's shape", target_batch.shape)

                seq, peds, coords = train_batch.shape # q is number of pedestrians

                #forward pass
                out = vanilla_lstm_net(train_batch, pred_len=pred_len) # forward pass of lstm network for training
                print("out's shape:", out.shape)
                optimizer.zero_grad() # zero out gradients
                cur_train_loss = criterion(out, target_batch) # calculate MSE loss
                print('Current training loss: {}'.format(cur_train_loss.item())) # print current training loss
                #calculating average deisplacement error
                out1=out
                target_batch1=target_batch  #making a copy of the tensors to convert them to array
                avgD_error=(np.sum(np.sqrt(np.square(out1[:,:,0].detach().numpy()-target_batch1[:,:,0].detach().numpy())+
                    np.square(out1[:,:,1].detach().numpy()-target_batch1[:,:,1].detach().numpy()))))/(pred_len*peds)
                train_avgD_error.append(avgD_error)
                print("current avg Disp error:",avgD_error)
                #calculating final displacement error
                finalD_error=(np.sum(np.sqrt(np.square(out1[pred_len-1,:,0].detach().numpy()-target_batch1[pred_len-1,:,0].detach().numpy())+
                    np.square(out1[pred_len-1,:,1].detach().numpy()-target_batch1[pred_len-1,:,1].detach().numpy()))))/peds
                train_finalD_error.append(finalD_error)
                print("current final displacement error:",finalD_error)

                train_loss.append(cur_train_loss.item())
                cur_train_loss.backward() # backward prop
                optimizer.step() # step like a mini-batch (after all pedestrians)
                ### end prototyping ###

            return cur_train_loss
        optimizer.step(closure) # update weights

        # save model at every epoch (uncomment) 
        # torch.save(vanilla_lstm_net, './saved_models/vanilla_lstm_model_lr0005.pt')
        # print("Saved vanilla_lstm_net!")
        avg_train_loss.append(np.sum(train_loss)/len(train_loss))
        avg_train_avgD_error.append(np.sum(train_avgD_error)/len(train_avgD_error))
        avg_train_finalD_error.append(np.sum(train_finalD_error)/len(train_finalD_error))   
        std_train_loss.append(np.std(np.asarray(train_loss)))
        train_loss = [] # empty train loss

        print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")
        print("average train loss: {}".format(avg_train_loss))
        print("average std loss: {}".format(std_train_loss))
        avg_test_loss.append(test(vanilla_lstm_net,args)) ##calliing test function to return avg test loss at each epoch


    # all epochs have ended, so now save your model
    torch.save(vanilla_lstm_net, './saved_models/Vlstm_model_lr0005_ep5.pt')
    print("Saved vanilla_lstm_net!" + './saved_models/Vlstm_model_lr0005_ep5.pt')
    
    ''' visualize losses vs. epoch'''

    plt.figure() # new figure
    plt.title("Average train & test loss v/s epoch {} epochs".format(num_epoch))
    plt.plot(avg_train_loss,label='avg train_loss') 
    plt.plot(avg_test_loss,color='red',label='avg test_loss')
    plt.legend()
    plt.show(block=True)
    # plt.show()


    plt.figure() # new figure
    plt.title("Average and final displacement error {} epochs".format(num_epoch))
    plt.plot(avg_train_finalD_error,label='final displacement error') 
    plt.plot(avg_train_avgD_error,color='red',label='avg displacement error')
    plt.legend()
    plt.show(block=True)

    #visualizing std deviation v/s epoch
    plt.figure()
    plt.title("Std of train loss vs epoch")
    plt.plot(std_train_loss)
    plt.show(block=True)
    # plt.show()

# main function

if __name__ == '__main__':
    main(args)

