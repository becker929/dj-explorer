# dj-explorer

A web app for exploring DJ mixes from SoundCloud, made in Flask with Flask-SocketIO. The search is based on the text descriptions of mixes and it is capable of finding mixes when given a track as well as finding tracks when given a mix. No fancy audio-based search, for now.



## How to run

### Pull the repo

```
git clone https://github.com/becker929/dj-explorer
```

### Install pyenv and pyenv virtualenv

(on MacOS)

```
brew update
brew install pyenv
brew install pyenv-virtualenv
pyenv virtualenv-init # make sure that your ~/.zshrc is correct (see becker929/dev-env)
```

### Create a virtual environment and install dependencies

```
pyenv install python 3.10.2
pyenv virtualenv 3.10.2 dje
pyenv activate dje
python -m pip install --upgrade pip     
python -m pip install -r requirements.txt
```

### Run the server

```
flask shell
```

This will run the Flask server, which can the be accessed via the browser at http://0.0.0.0:80/mix-explorer . 



I am running this on a Google Compute Engine Linux VM and serving it at http://anthonybecker.xyz/mix-explorer . 

Example search: http://anthonybecker.xyz/mix-explorer/example .

You can also find my resume at http://anthonybecker.xyz/resume . 


