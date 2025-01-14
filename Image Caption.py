# linear algebra
import numpy as np

# data processing, CSV file I/O
import pandas as pd
import os
import string
import tensorflow as tf
from tqdm import tqdm
from textwrap import wrap
from keras.preprocessing.image import ImageDataGenerator
from keras_preprocessing.sequence import pad_sequences
from keras.preprocessing.text import Tokenizer
from keras.models import Sequential, Model
from keras.layers import (
    Conv2D,
    MaxPooling2D,
    GlobalAveragePooling2D,
    Flatten,
    Dense,
    LSTM,
    Dropout,
    Embedding,
    Activation,
    Concatenate,
    BatchNormalization,
    Input,
    add,
    Layer,
    Reshape,
    concatenate,
    Bidirectional,
)
from keras.utils import to_categorical, Sequence, load_img, img_to_array, plot_model
from keras.applications import VGG16, ResNet50, DenseNet201
from keras.optimizers import Adam
from keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau
import warnings
import matplotlib.pyplot as plt
import seaborn as sns

plt.rcParams["font.size"] = 12
sns.set_style("dark")
warnings.filterwarnings("ignore")


"""Image Captioning"""
image_path = (
    "/Users/ljnz1314/Documents/Machine learning/Image Caption Generator/Images/"
)

data = pd.read_csv(
    "/Users/ljnz1314/Documents/Machine learning/Image Caption Generator/captions.txt"
)
data.head()


def readImage(path, img_size=224):
    img = load_img(path, color_mode="rgb", target_size=(img_size, img_size))
    img = img_to_array(img)
    img = img / 255

    return img


"""Visualization"""


def display_images(temp_df):
    temp_df = temp_df.reset_index(drop=True)
    plt.figure(figsize=(20, 20))
    n = 0
    for i in range(15):
        n += 1
        plt.subplot(5, 5, n)
        plt.subplots_adjust(hspace=0.7, wspace=0.3)
        image = readImage(f"{image_path}/{temp_df.image[i]}")
        plt.imshow(image)
        plt.title("\n".join(wrap(temp_df.caption[i], 20)))
        plt.axis("off")
        # plt.show()


display_images(data.sample(15))


"""Caption Text Preprocessing Steps"""


def text_preprocessing(data):
    data["caption"] = data["caption"].apply(lambda x: x.lower())
    data["caption"] = data["caption"].apply(lambda x: x.replace("[^A-Za-z]", ""))
    data["caption"] = data["caption"].apply(lambda x: x.replace("\s+", " "))
    data["caption"] = data["caption"].apply(
        lambda x: " ".join([word for word in x.split() if len(word) > 1])
    )
    data["caption"] = "startseq " + data["caption"] + " endseq"
    return data


"""Preprocessed Text"""
data = text_preprocessing(data)
captions = data["caption"].tolist()


"""Tokenization and Encoded Representation"""
tokenizer = Tokenizer()
tokenizer.fit_on_texts(captions)
vocab_size = len(tokenizer.word_index) + 1
max_length = max(len(caption.split()) for caption in captions)

images = data["image"].unique().tolist()
nimages = len(images)

split_index = round(0.85 * nimages)
train_images = images[:split_index]
val_images = images[split_index:]

train = data[data["image"].isin(train_images)]
test = data[data["image"].isin(val_images)]

train.reset_index(inplace=True, drop=True)
test.reset_index(inplace=True, drop=True)

tokenizer.texts_to_sequences([captions[1]])


"""Image Feature Extraction"""
model = DenseNet201()
fe = Model(inputs=model.input, outputs=model.layers[-2].output)

img_size = 224
features = {}
for image in tqdm(data["image"].unique().tolist()):
    img = load_img(os.path.join(image_path, image), target_size=(img_size, img_size))
    img = img_to_array(img)
    img = img / 225
    img = np.expand_dims(img, axis=0)
    feature = fe.predict(img, verbose=0)
    features[image] = feature

"""Data Generation"""


class CustomDataGenerator(Sequence):

    def __init__(
        self,
        df,
        X_col,
        y_col,
        batch_size,
        directory,
        tokenizer,
        vocab_size,
        max_length,
        feature,
        shuffle=True,
    ):
        self.df = df.copy()
        self.X_col = X_col
        self.y_col = y_col
        self.directory = directory
        self.batch_size = batch_size
        self.tokenizer = tokenizer
        self.vocab_size = vocab_size
        self.max_length = max_length
        self.features = features
        self.shuffle = shuffle
        self.n = len(self.df)

    def on_epoch_end(self):
        self.df = self.df.sample(frac=1).reset_index(drop=True)

    def __len__(self):
        return self.n // self.batch_size

    def __getitem__(self, index):
        batch = self.df.iloc[index * self.batch_size : (index + 1) * self.batch_size, :]
        X1, X2, y = self.__get_data(batch)
        return (X1, X2), y

    def __get_data(self, batch):
        X1, X2, y = list(), list(), list()
        images = batch[self.X_col].tolist()

        for image in images:
            features = self.features[images][0]
            captions = batch.loc[batch[self.X_col] == image, self.y_col].tolist()
            for caption in captions:
                seq = self.tokenizer.texts_to_sequences([caption])[0]

                for i in range(1, len(seq)):
                    in_seq, out_seq = seq[:i], seq[i]
                    in_seq = pad_sequences([in_seq], maxlen=self.max_length)[0]
                    out_seq = to_categorical([out_seq], num_classes=self.vocab_size)[0]
                    X1.append(feature)
                    X2.append(in_seq)
                    y.append(out_seq)

        X1, X2, y = np.array(X1), np.array(X2), np.array(y)

        return X1, X2, y


"""Modelling"""
input1 = Input(shape=(1920,))
input2 = Input(shape=(max_length,))

img_features = Dense(256, activation="relu")(input1)
img_features_reshaped = Reshape((1, 256), input_shape=(256,))(img_features)

sentence_features = Embedding(vocab_size, 256, mask_zero=False)(input2)
merged = concatenate([img_features_reshaped, sentence_features], axis=1)
sentence_features = LSTM(256)(merged)
x = Dropout(0.5)(sentence_features)
x = add([x, img_features])
x = Dense(128, activation="relu")(x)
x = Dropout(0.5)(x)
output = Dense(vocab_size, activation="softmax")(x)

caption_model = Model(inputs=[input1, input2], outputs=output)
caption_model.compile(loss="categorical_crossentropy", optimizer="adam")

"""Model Modification"""
plot_model(caption_model)
caption_model.summary()

train_generator = CustomDataGenerator(
    df=train,
    X_col="image",
    y_col="caption",
    batch_size=64,
    directory=image_path,
    tokenizer=tokenizer,
    vocab_size=vocab_size,
    max_length=max_length,
    features=features,
)
validation_generator = CustomDataGenerator(
    df=test,
    X_col="image",
    y_col="caption",
    batch_size=64,
    directory=image_path,
    tokenizer=tokenizer,
    vocab_size=vocab_size,
    max_length=max_length,
    features=features,
)

model_name = "model.h5"
checkpoint = ModelCheckpoint(
    model_name, monitor="val_loss", mode="min", save_best_only=True, verbose=1
)

earlystopping = EarlyStopping(
    monitor="val_loss", min_delta=0, patience=5, verbose=1, restore_best_weights=True
)

learning_rate_reduction = ReduceLROnPlateau(
    monitor="val_loss", patience=3, verbose=1, factor=0.2, min_lr=0.00000001
)

history = caption_model.fit(
    train_generator,
    epochs=50,
    validation_data=validation_generator,
    callbacks=[checkpoint, earlystopping, learning_rate_reduction],
)

"""Learning Curve"""
plt.figure(figsize=(20, 8))
plt.plot(history.history["loss"])
plt.plot(history.history["val_loss"])
plt.title("model loss")
plt.ylabel("loss")
plt.xlabel("epoch")
plt.legend(["train", "val"], loc="upper left")
plt.show()

"""Caption Generation Utility Functions"""


def idx_to_word(integer, tokenizer):
    for word, index in tokenizer.word_index.items():
        if index == integer:
            return word
    return None


def predict_caption(model, image, tokenizer, max_length, features):
    feature = features[image]
    in_text = "startseq"
    for i in range(max_length):
        sequence = tokenizer.texts_to_sequences([in_text])[0]
        sequence = pad_sequences([sequence], max_length)

        y_pred = model.predict([feature, sequence])
        y_pred = np.argmax(y_pred)

        word = idx_to_word(y_pred, tokenizer)

        if word is None:
            break

        in_text += " " + word

        if word == "endseq":
            break
    return in_text


"""Taking 15 Random Samples for Caption Prediction¶"""
samples = test.sample(15)
samples.reset_index(drop=True, inplace=True)

for index, record in samples.iterrows():
    img = load_img(os.path.join(image_path, record["image"]), target_size=(224, 224))
    img = img_to_array(img)
    img = img / 255

    caption = predict_caption(caption_model, record["image"], target_size=(224, 224))
    samples.loc[index, "caption"] = caption

"""Results"""
display_images(samples)
