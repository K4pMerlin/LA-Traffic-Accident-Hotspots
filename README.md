# LA-Traffic-Accident-Hotspots
## Predicting Weekly Traffic Accident Hotspots (Los Angeles)

## 📌 Overview
This project predicts the Top-10 highest-risk 1km x 1km grid cells for traffic accidents in Los Angeles for the following week. We compare traditional statistical models, deep learning models (CNN, ConvLSTM), and a novel LLM-based feature extraction pipeline (System-1).

## 📊 Dataset
- **Source**: [Hugging Face - US Accidents](填上你的数据链接)
- **Scale**: 156,491 accident records across 563 candidate 1km cells.
- **Time Split**: Chronological split (207 training weeks, 69 validation weeks, 70 test weeks).

## 🧠 System-1 Innovation (LLM Text Extraction)
We utilize a Large Language Model (`StartLLM-Decisions-8B-instruct`) to extract probabilistic closure features from free-text accident descriptions. We conducted a rigorous paired test to evaluate its impact on Average Precision (AP) and Top-10 Coverage.

## 📈 Results Summary
- **Top-10 Coverage**: Best achieved by Raw-History CNN and CNN + 8-32 week rate (14.74%).
- **Average Precision (AP)**: System-1 text features improved AP in 11 out of 12 models, proving its capability in overall risk ranking.
*(这里可以插入你 PPT 里的两张漂亮的柱状图)*

## 📂 Repository Structure
(此处可以列出你的文件夹结构说明，方便别人看懂)

## 🚀 How to Run
(在这里教别人怎么运行你的代码，比如 `pip install -r requirements.txt` 等)

## 👥 Authors
(填上你和你队友的名字)
