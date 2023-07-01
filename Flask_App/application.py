from flask import Flask, render_template
import urllib.request
from bs4 import BeautifulSoup
from transformers import pipeline

# Create Flask app
app = Flask(__name__, template_folder='.')
containers = []
link_number = 0


# Route for the homepage
@app.route('/')
def index():
    return render_template('index.html', containers=containers)


@app.route('/get_news', methods=['POST'])
def create_containers():
    global containers
    containers = get_data()
    return render_template('index.html', containers=containers)


# Function to scrape links of articles from Al Jazeera main page
def get_links():
    # Al jazeera Europe first page
    req = urllib.request.Request('https://www.aljazeera.com/news/')
    page = urllib.request.urlopen(req)
    soup = BeautifulSoup(page.read(), 'html.parser')

    # Get links into a list
    link = []
    raw_links = soup.find_all('a', class_='u-clickable-card__link')
    for raw_link in raw_links:
        link.append('https://www.aljazeera.com' + raw_link.get('href'))

    return link


# Function to scrape articles and get chunks of text from a list of links
def get_data():
    # Retrieve links from Al Jazeera main page
    global link_number
    urls = get_links()
    amount_of_links = len(urls) - 1

    # Article load
    req = urllib.request.Request(urls[link_number])
    page = urllib.request.urlopen(req)
    soup = BeautifulSoup(page.read(), 'html.parser')

    # Title of the article
    title = soup.find_all(['h1'])
    title = title[0].text

    # Image and description of the article
    img = soup.find('img', {'fetchpriority': 'high'})

    # In case image is not found, or alt text is not found
    try:
        image_text = img['alt']
    except:
        image_text = ''
    try:
        image_url = 'https://www.aljazeera.com' + img['src']
    except:
        image_url = ''

    # Text of the article
    results = soup.find_all(['p', 'li'])
    text = [results.text for results in results]
    article = ' '.join(text)
    article = article.replace('.', '.<end>')
    article = article.replace('!', '?<end>')
    article = article.replace('?', '!<end>')
    sentences = article.split('<end>')
    del sentences[-1]  # Last sentence is not useful

    # Splitting sentences into chunks
    max_chunk = 500
    chunks = []
    current_chunk = 0

    # Split sentences into chunks with a maximum length of `max_chunk`
    for sentence in sentences:
        if len(chunks) == current_chunk + 1:
            # Extend the current chunk if it can accommodate the sentence
            if len(chunks[current_chunk]) + len(sentence.split(' ')) <= max_chunk:
                chunks[current_chunk].extend(sentence.split(' '))
            else:
                # Move to the next chunk if the current one is full
                current_chunk += 1
                chunks.append(sentence.split(' '))
        else:
            chunks.append(sentence.split(' '))
    # Join the words in each chunk back into sentences
    for chunk_id in range(len(chunks)):
        chunks[chunk_id] = ' '.join(chunks[chunk_id])
    # Summarize the chunks using the BART model
    all_sentences_summ, image_text_summ = summarize(chunks, image_text)

    # Create container with article details
    containers.append({
        'text': title,
        'link': urls[link_number],
        'image_url': image_url,
        'image_text': image_text_summ,
        'all_sentences': all_sentences_summ
    })
    link_number += 1
    return containers


# Function to summarize text using the BART model
def summarize(chunks, image_text):
    # Summarize text in chunks
    summarizer = pipeline('summarization', model="facebook/bart-large-cnn")
    sentence_res = summarizer(chunks, max_length=90, min_length=20, do_sample=False)
    all_sentences_summ = ' '.join([summ['summary_text'] for summ in sentence_res])
    all_sentences_summ = all_sentences_summ.replace(' .', '.')

    # Summarize alt text in image
    image_text_res = summarizer(image_text, max_length=36, min_length=0, do_sample=False)
    image_text_summ = ' '.join([summ['summary_text'] for summ in image_text_res])
    image_text_summ = image_text_summ.replace(' .', '.')

    return all_sentences_summ, image_text_summ


if __name__ == '__main__':
    app.run(debug=True)
