# VLQA
Website/Learderboard, Starter Code and Data for Visuo-Linguistic Question Answering (VLQA), Findings of EMNLP 2020

Visuo-Linguistic Question Answering (VLQA) is a dataset for joint reasoning over visuo-linguistic context.

# Website/Leaderboard: 
https://shailaja183.github.io/vlqa/

# Explore Dataset: 
https://shailaja183.github.io/vlqa/dataset.html

# Download Dataset: 
Train Set [xxx MB], Val Set [xxx MB] and Images [xxx GB]

# Starter Code: 
Code for multimodal baselines HOLE (method proposed in the paper), LXMERT, ViLBERT, VLBERT, VisualBERT and DQA-Net is available at
https://github.com/shailaja183/vlqa/baselines (coming soon)

# Paper and Supplementary Material:
https://arxiv.org/pdf/2005.00330.pdf

# Evaluating a Model:
Download Evaluation Script and sample Prediction file 
Evaluation Script: https://shailaja183.github.io/vlqa/static/evaluate.py
Sample Prediction file: https://shailaja183.github.io/vlqa/static/sample_predictions.json
Then run following command to see the accuracy on Val set;
python evaluate.py {path-to-prediction-file} {path-to-validation-set}

# Submit your Model:
Once you are satisfied with your model performance on the validation set, use the following tutorial to submit it for an official evaluation on the test set.
https://worksheets.codalab.org/worksheets/0x31e65ec372c4499b9b53b78e5551c6eb

# Citation
If you find our dataset or model helpful, please cite our paper :-)
@misc{sampat2020diverse,
title={Visuo-Linguistic Question Answering (VLQA) Challenge},
author={Shailaja Sampat, Yezhou Yang and Chitta Baral},
year={2020},
eprint={2005.00330},
archivePrefix={arXiv},
primaryClass={cs.CV}
}
