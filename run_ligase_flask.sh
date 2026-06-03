#!/bin/bash

SESSION_NAME="ligase_flask"
CONDA_ENV="viraldb"

PROJECT_DIR="/mnt/c/Users/joeys/Documents/WorkingViralDB/Ligases/MODULE/e3-recruiter-mod"
APP_CMD="python Ligase_app.py"

tmux has-session -t $SESSION_NAME 2>/dev/null

if [ $? != 0 ]; then
    echo "🚀 Starting new tmux session: $SESSION_NAME"

    tmux new-session -d -s $SESSION_NAME \
        "source ~/miniconda3/etc/profile.d/conda.sh \
         && conda activate $CONDA_ENV \
         && cd $PROJECT_DIR \
         && $APP_CMD"
else
    echo "Session '$SESSION_NAME' is already running."
fi
