import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lumen_project.settings')
django.setup()

from core.models import Flashcard
from django.contrib.auth.models import User

jasmine  = User.objects.get(id=5)
jasmine08 = User.objects.get(id=7)

cards_data = [
    # Data Science
    ('Data Science', 'What is a confusion matrix?', 'A table evaluating classification model performance showing TP, TN, FP, FN counts'),
    ('Data Science', 'What does overfitting mean in ML?', 'When a model learns training data including noise, performing poorly on unseen data'),
    ('Data Science', 'What is cross-validation?', 'Evaluating models by splitting data into k folds and training/testing on each fold'),
    ('Data Science', 'Define precision in classification', 'Precision = TP / (TP + FP) — fraction of positive predictions that are actually correct'),
    ('Data Science', 'Define recall in classification', 'Recall = TP / (TP + FN) — fraction of actual positives correctly identified'),
    ('Data Science', 'What is the bias-variance tradeoff?', 'The balance between underfitting (high bias) and overfitting (high variance)'),
    ('Data Science', 'What is feature engineering?', 'Using domain knowledge to create or transform features to improve model performance'),
    ('Data Science', 'What is a ROC curve?', 'A plot of True Positive Rate vs False Positive Rate at various classification thresholds'),
    ('Data Science', 'What does AUC stand for?', 'Area Under the Curve — measures classifier performance; 1.0 is perfect, 0.5 is random'),
    ('Data Science', 'What is regularisation in ML?', 'Techniques like L1/L2 that penalise model complexity to reduce overfitting'),

    # Python Programming
    ('Python Programming', 'What is a list comprehension?', 'A concise way to create lists: [expression for item in iterable if condition]'),
    ('Python Programming', 'What does len() return for a string?', 'The number of characters including spaces and punctuation'),
    ('Python Programming', 'What is a lambda function?', 'An anonymous single-expression function: lambda x: x*2'),
    ('Python Programming', 'Difference between == and is in Python?', '== checks value equality; is checks if two variables point to the same object in memory'),
    ('Python Programming', 'What does *args do in a function?', 'Allows passing a variable number of positional arguments packed into a tuple'),
    ('Python Programming', 'What is a Python decorator?', 'A function that wraps another function to add behaviour without modifying its source code'),
    ('Python Programming', 'What is the GIL in Python?', 'Global Interpreter Lock — prevents multiple threads from executing Python bytecode simultaneously'),
    ('Python Programming', 'What does zip() do?', 'Combines multiple iterables into an iterator of tuples pairing corresponding elements'),
    ('Python Programming', 'What is a generator in Python?', 'A function using yield that lazily produces values one at a time instead of a full list'),
    ('Python Programming', 'What does enumerate() do?', 'Adds a counter to an iterable, returning (index, value) pairs'),

    # Machine Learning
    ('Machine Learning', 'What is gradient descent?', 'An optimisation algorithm minimising loss by iteratively moving in the direction of steepest descent'),
    ('Machine Learning', 'What is a learning rate?', 'A hyperparameter controlling step size during gradient descent optimisation'),
    ('Machine Learning', 'What is a neural network?', 'Interconnected layers of nodes inspired by the brain that learn patterns from data'),
    ('Machine Learning', 'What is backpropagation?', 'Computing gradients of the loss with respect to weights by applying the chain rule backwards'),
    ('Machine Learning', 'What is dropout regularisation?', 'Randomly deactivating neurons during training to prevent overfitting'),
    ('Machine Learning', 'What is a support vector machine?', 'A classifier that finds the optimal hyperplane maximising the margin between class boundaries'),
    ('Machine Learning', 'What is k-means clustering?', 'An unsupervised algorithm partitioning data into k clusters by minimising within-cluster variance'),
    ('Machine Learning', 'What is transfer learning?', 'Using a pre-trained model on a new task, fine-tuning it with less data and compute'),
    ('Machine Learning', 'What is the vanishing gradient problem?', 'Gradients become very small in deep networks, making early layers learn very slowly'),
    ('Machine Learning', 'What is an epoch in training?', 'One complete pass through the entire training dataset during model optimisation'),

    # Statistics
    ('Statistics', 'What is the central limit theorem?', 'The mean of a large sample from any distribution is approximately normally distributed'),
    ('Statistics', 'What is a p-value?', 'The probability of observing results at least as extreme assuming the null hypothesis is true'),
    ('Statistics', 'What is standard deviation?', 'A measure of data spread around the mean; square root of variance'),
    ('Statistics', 'What is a null hypothesis?', 'The default assumption that there is no effect or difference between groups being tested'),
    ('Statistics', 'What is Bayesian inference?', 'Updating prior beliefs with new evidence using Bayes theorem to form posterior probabilities'),
    ('Statistics', 'What is a confidence interval?', 'A range likely containing the true population parameter with a stated probability'),
    ('Statistics', 'What is Type I error?', 'Rejecting a true null hypothesis — also called a false positive'),
    ('Statistics', 'What is Type II error?', 'Failing to reject a false null hypothesis — also called a false negative'),
    ('Statistics', 'What is correlation?', 'A measure of the linear relationship between two variables, ranging from -1 to +1'),
    ('Statistics', 'What is the normal distribution?', 'A symmetric bell-shaped probability distribution defined by mean and standard deviation'),

    # Mathematics
    ('Mathematics', 'What is a derivative?', 'The rate of change of a function with respect to a variable; slope of the tangent at a point'),
    ('Mathematics', 'What is an integral?', 'The area under a curve; the reverse operation of differentiation'),
    ('Mathematics', 'What is the Pythagorean theorem?', 'In a right triangle: a squared + b squared = c squared, where c is the hypotenuse'),
    ('Mathematics', 'What is a matrix?', 'A rectangular array of numbers in rows and columns used in linear algebra'),
    ('Mathematics', 'What is an eigenvalue?', 'A scalar lambda where Av = lambda*v for matrix A and non-zero vector v'),
    ('Mathematics', 'What is a prime number?', 'A natural number greater than 1 with no divisors other than 1 and itself'),
    ('Mathematics', 'What is a logarithm?', 'The inverse of exponentiation: log base b of x = y means b to the power y = x'),
    ('Mathematics', 'What is a vector?', 'A quantity with both magnitude and direction, represented as an array of numbers'),
    ('Mathematics', 'What is a limit in calculus?', 'The value a function approaches as the input approaches a given point'),
    ('Mathematics', 'What is the chain rule?', 'Derivative of a composite function: d/dx[f(g(x))] = f prime(g(x)) times g prime(x)'),

    # Computer Science
    ('Computer Science', 'What is Big O notation?', 'A way to describe worst-case time or space complexity of an algorithm'),
    ('Computer Science', 'What is a binary search tree?', 'A tree where each node has at most two children and left < node < right'),
    ('Computer Science', 'What is a hash table?', 'A data structure mapping keys to values using a hash function for O(1) average lookup'),
    ('Computer Science', 'What is recursion?', 'A function that calls itself to solve smaller subproblems until a base case is reached'),
    ('Computer Science', 'What is dynamic programming?', 'Storing solutions to overlapping subproblems to avoid redundant computation'),
    ('Computer Science', 'What is an API?', 'Application Programming Interface — a contract defining how software components communicate'),
    ('Computer Science', 'What is a database index?', 'A data structure that speeds up queries by allowing fast lookup without full table scans'),
    ('Computer Science', 'What is object-oriented programming?', 'A paradigm organising code into objects with attributes (state) and methods (behaviour)'),
    ('Computer Science', 'What is TCP/IP?', 'A suite of protocols defining how data is transmitted over the internet in packets'),
    ('Computer Science', 'Difference between stack and heap memory?', 'Stack is LIFO for function frames (fast); heap is for dynamic allocation (flexible, slower)'),
]

created = skipped = 0
for subject, front, back in cards_data:
    for user in [jasmine, jasmine08]:
        obj, was_created = Flashcard.objects.get_or_create(
            user=user, front=front,
            defaults={'back': back, 'subject': subject}
        )
        if was_created:
            created += 1
        else:
            skipped += 1

subjects = set(s for s, f, b in cards_data)
print(f'Created {created} new flashcards, skipped {skipped} existing.')
print(f'Subjects: {", ".join(sorted(subjects))}')
print(f'Total per user: {len(cards_data)} cards across {len(subjects)} subjects')
