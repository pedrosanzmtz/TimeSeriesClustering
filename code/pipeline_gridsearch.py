from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import accuracy_score
from sklearn.externals import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import Imputer
from sklearn import svm
from sklearn.metrics import mean_squared_error
from pprint import pprint
import numpy as np
import pandas as pd
from time import time
from scipy import stats
import pywt


def get_pipes(random_state):
    pipes = dict()
    pipes["lr"] = Pipeline([('scl', StandardScaler()),
                        ('clf', LogisticRegression(random_state=random_state))])


    pipes["rf"] = Pipeline([('scl', StandardScaler()),
                        ('clf', RandomForestClassifier(random_state=random_state))])


    pipes["svm"] = Pipeline([('scl', StandardScaler()),
                        ('clf', svm.SVC(random_state=random_state))])


    pipes["mlp"] = Pipeline([('scl', StandardScaler()),
                        ('clf', MLPClassifier(random_state=random_state))])
    return pipes

def get_grids():
    grids = dict()
    grids["lr"] = [{'clf__penalty': ['l2'],
                        'clf__C': [0.3, 0.5, 1],
                       'clf__solver': ['lbfgs', 'newton-cg']}] 

    grids["rf"] = [{'clf__criterion': ['gini', 'entropy'],
                       'clf__n_estimators': [10, 20, 30]}]

    grids["svm"] = [{'clf__kernel': ['sigmoid', 'rbf'], 
                        'clf__C': [0.3, 0.5, 1]}]

    grids["mlp"] = [{'clf__activation': ['logistic', 'relu'],
                        'clf__solver': ['sgd', 'adam'],
                        'clf__hidden_layer_sizes': [(10, ), (10, 5)]}]
    return grids

def generate_pipeline(cv, jobs=-1, random_state=42):
    # Construct some pipelines
    pipes = get_pipes(random_state)        
    grids = get_grids()
    
    # Construct grid searches
    gs_lr = GridSearchCV(estimator=pipes["lr"],
                         param_grid=grids["lr"],
                         scoring='accuracy',
                         cv=cv) 

    gs_rf = GridSearchCV(estimator=pipes["rf"],
                         param_grid=grids["rf"],
                         scoring='accuracy',
                         cv=cv, 
                         n_jobs=jobs)

    gs_svm = GridSearchCV(estimator=pipes["svm"],
                          param_grid=grids["svm"],
                          scoring='accuracy',
                          cv=cv,
                          n_jobs=jobs)

    gs_mlp = GridSearchCV(estimator=pipes["mlp"],
                          param_grid=grids["mlp"],
                          scoring='accuracy',
                          cv=cv)

    # List of pipelines for ease of iteration
    grids = [gs_lr, gs_rf, gs_svm, gs_mlp]
    # Dictionary of pipelines and classifier types for ease of reference
    grid_dict = {0: 'LR', 
                 1: 'RF', 
                 2: 'SVM',
                 3: 'MLP'}
    return (grids, grid_dict)


def run_pipeline(X, y, cv, out, sub, name):
    # Fit the grid search objects
    (grids, grid_dict) = generate_pipeline(cv, jobs=-1, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.33, random_state=42)
    y_test = y_test.values
    print('Performing model optimizations...')
    best_acc = 0.0
    best_clf = 0
    best_gs = ''
    for idx, gs in enumerate(grids):
        initial_time = time()
        gs_out_name = '../results/models/' + grid_dict[idx] + '_' + name + '.csv'
        gs_out = open(gs_out_name, 'w')
        gs_out_count_name = "../results/counts/count_" + grid_dict[idx] + '_' + name + '.csv'
        gs_out_count = open(gs_out_count_name, "w")
        print('\nEstimator: %s' % grid_dict[idx])	
        # Fit grid search	
        toi = time()
        gs.fit(X_train, y_train)
        tof = time() - toi 
        # Best params
        print('Params Test:')
        means = gs.cv_results_['mean_test_score']
        stds = gs.cv_results_['std_test_score']
        
        get_results(means, stds, gs, gs_out)
        
        print('Best params: %s' % gs.best_params_)
        # Best training data accuracy
        print('Best training accuracy: %.3f' % gs.best_score_)
        # Predict on test data with best params
        y_pred = gs.predict(X_test)

        count_results(gs_out_count, y_pred, y_test)

        # Test data accuracy of model with best params
        acc = '%.2f' % accuracy_score(y_test, y_pred)
        mse = '%.3f' % mean_squared_error(y_test, y_pred)
        total = str(y_test.shape[0])
        acc_n = str(int(y_test.shape[0] * float(acc)))
        total_time = '%.2f' % (time() - initial_time)
        print('Test set accuracy score for best params:', acc)
        print('Test set mse score for best params:', mse)
        print('Total time:', total_time)
        # Track best (highest test accuracy) model
        out.write(grid_dict[idx] + ',' + sub + ',' + acc + ',' + mse + ',' + total_time + '\n')


def preprocess(X, na_values):
    imp = Imputer(missing_values=na_values, strategy='mean', axis=1)
    
    imp.fit(X)
    X = imp.transform(X)

    X, _ = pywt.dwt(X, 'db1')

    X_stats = stats.describe(X, axis=1)

    X = pd.DataFrame({'min': X_stats.minmax[0], 'max': X_stats.minmax[1], 
                      'kurtosis': X_stats.kurtosis, 'skewness': X_stats.skewness, 
                      'variance': X_stats.variance, 'mean': X_stats.mean})
    return X


def count_results(gs_out_count, y_pred, y_test):
    # Count false/positive for each class
    gs_out_count.write("Class,Correct,incorrect\n")
    for i in np.unique(y_pred):
        i_test = y_test == i
        i_pred = y_pred == i
        i_correct = i_test == i_pred
        i_correct = i_correct[i_pred]
        i_incorrect = i_correct.shape[0] - np.sum(i_correct)
        gs_out_count.write(str(i) + "," + str(np.sum(i_correct)) + "," + str(i_incorrect) + "\n")
    gs_out_count.close()


def get_results(means, stds, gs, gs_out):
    for mean, std, params in zip(means, stds, gs.cv_results_['params']):
        print("%0.3f (+/-%0.03f) for %r" % (mean, std * 2, params))
        for p in params:
            gs_out.write(str(params[p]) + ',')
        gs_out.write(str(mean) + '\n')
    gs_out.close()
