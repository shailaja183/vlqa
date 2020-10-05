import json
import sys

def evaluate(pred_file, truth_file):
    gt_answers = []
    correct=0
    
    with open(truth_file, 'r') as j:
        gt_data = json.loads(j.read())
    j.close()
    for d in gt_data:
        gt_answers.append(d["answer"])
    print(gt_answers)

    with open(pred_file,'r') as j2:
        pred_data = json.loads(j2.read())
    j2.close()
    pred_answers = pred_data["val"]
    print(pred_answers)

    if len(gt_answers)==len(pred_answers):
        for a,g in zip(gt_answers, pred_answers):
            if a==g:
                correct+=1
        print(correct,'out of', len(gt_answers),'predicted correctly.')
        print('Accuracy', round((float(correct)*100)/len(gt_answers),2),'%')
    else:
        print('Length mismatch, prediction file must have',len(gt_answers),'entries.')

#evaluate('sample_predictions.json', 'val.json')
evaluate(sys.argv[1], sys.argv[2])

