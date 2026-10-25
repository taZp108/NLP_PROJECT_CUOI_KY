from collections import Counter, defaultdict
import math

class HMM_NER:
    def __init__(self, smoothing=1e-8):
        self.smoothing = smoothing #Hệ số Laplace làm mịn

        #Đếm số lần xuất hiện của các tag và token
        self.trans_count = defaultdict(Counter) #Đếm số chuyển trạng thái tag_t -> tag_t+1
        self.emit_count  = defaultdict(Counter) #Đếm số phát xạ từ tag_t -> token_t
        self.start_count = Counter() #Đếm số lần tag_t là tag đầu tiên trong câu
        self.end_count   = Counter() #Đếm số lần tag_t là tag cuối cùng trong câu
        #Lý do sử dụng defaultdict(Counter) để dễ dàng đếm số lần xuất hiện của các tag và token mà không cần kiểm tra xem key đã tồn tại chưa

        #Tính xác suất chuyển trạng thái, phát xạ, bắt đầu và kết thức sau khi training
        self.log_trans = {} #Xác suất chuyển trạng thái (Transition) log P(tag_t+1|tag_t)
        self.log_emit  = {} #Xác suât phát xạ (Emission) log P(token_t|tag_t)
        self.log_start = {} #Xác suất bắt đầu log P(tag_t) khi tag_t là tag đầu tiên trong câu
        self.log_end   = {} #Xác suất kết thúc log P(tag_t) khi tag_t là tag cuối cùng trong câu
        self.log_oov = {} #Xác suất cho các từ OOV (Out-of-vocabulary) (những từ ko xuất hiện trong train nhưng có trong test) 
        
        self.tags = [] #Danh sách cá tag trong tập
        self.vocab = set() #Tập từ vựng
        self.trained = False #Dùng để đánh dấu đã train hay chưa
    
    '''
    Cấu trúc của task: list các dict, mỗi dict cấu trúc:
    {
        "tokenized": [
            [("token1", start, end), ("token2", start, end)],....] Dòng 1/Câu 1
            [("token1", start, end), ("token2", start, end)],....] Dòng 2/Câu 2
        ]
        "bio": [
            ["B/I/O-Label","B/I/O-Label","B/I/O-Label",...] Dòng 1/Câu 1
            ["B/I/O-Label","B/I/O-Label","B/I/O-Label",...] Dòng 2/Câu 2
        ]
    }
    '''

    def fit(self, tasks):
        #Làm sạch bộ đếm nếu gọi fit() lại nhiều lần khi tuning
        self.trans_count.clear()
        self.emit_count.clear()
        self.start_count.clear()
        self.end_count.clear()
        self.log_trans.clear()
        self.log_emit.clear()
        self.log_start.clear()
        self.log_end.clear()
        self.log_oov.clear()
        self.vocab.clear()
        
        #Duyệt từng task
        for task in tasks:
            tokenized = task["tokenized"]
            bio = task["bio"]
            #Duyệt từng câu trong task
            for tokens, tags in zip(tokenized, bio):
            #zip(tokenized, bio) ghép tokenized[0] và bio[0] thành 1 tuple (list, list)
                words = [tok[0] for tok in tokens]

                #Đảm bảo word và tag khớp độ dài
                n = min(len(words), len(tags))
                if n == 0: continue #Tránh lỗi không trích xuất được tag hoặc word
                words, tags = words[:n], tags[:n] #Lấy đúng số lượng tag và word

                #Đếm start, end
                self.start_count[tags[0]] += 1
                self.end_count[tags[-1]] += 1

                #Đếm emission, transition
                for i in range(n):
                    w, t = words[i], tags[i]

                    #Emission P(word|tag)
                    self.emit_count[t][w] += 1
                    self.vocab.add(w) #Add vào tập từ vựng (để biết từ nào đã từng xuất hiện)

                    #Transition P(tag_i|tag_i-1)
                    if i > 0: #Chỉ đếm khi i > 0 để loại start
                        self.trans_count[tags[i-1]][t] += 1

        #Chuẩn bị cho các xác suất
        self.tags = sorted(self.emit_count.keys())
        self._compute_log_probs() #Chuyển các count thành probability
        self.trained = True #Đánh dấu đã train


    def _compute_log_probs(self):
        '''
        Tính log các xác suất từ biến đếm và có thêm Laplace smoothing
        P(tag|tag_i-1) = (count(tag_i-1, tag_i) + smooth)
                         / (count(tag_i-1) + smooth * len(tag))
        P(word|tag) = (count(tag,word) + smooth)
                      / (count(tag) + smooth * (len(vocab) + 1))
        Chuyển sang logarit: Viberti nhân nhiều lần xác suất làm -> 0 -> underflow
        Laplace smoothing: 1 cặp (t, w) hoặc (prev, cur) chưa từng xuất hiện trong train 
                        -> count = 0 -> P = 0 -> log(0) -> Ảnh hưởng Viberti
        + smoothing vào tất cả count
        '''
        smooth = self.smoothing
        n = max(len(self.tags), 1)  #Số nhãn
        m = max(len(self.vocab), 1) #Kích thước vocab

        #P(start)
        total_start = sum(self.start_count.values()) or 1
        for t in self.tags:
            p = (self.start_count.get(t, 0) + smooth) / (total_start + smooth * n)
            self.log_start[t] = math.log(p)

        #P(end)
        total_end = sum(self.end_count.values()) or 1
        for t in self.tags:
            p = (self.end_count.get(t, 0) + smooth) / (total_end + smooth * n)
            self.log_end[t] = math.log(p)

        #Transition: P(tag_i|tag_i-1)
        for prev in self.tags:
            total_trans = sum(self.trans_count[prev].values()) or 1
            for cur in self.tags:
                p = (self.trans_count[prev].get(cur,0) + smooth) / (total_trans + smooth * n)
                self.log_trans[(prev, cur)] = math.log(p)

        #Emission: P(word|tag)
        for t in self.tags:
            total_emit = sum(self.emit_count[t].values()) or 1
            for w in self.vocab:
                p = (self.emit_count[t].get(w, 0) + smooth) / (total_emit + smooth*(m + 1))
                self.log_emit[(t, w)] = math.log(p)

            #Xác suất cho word ko trong vocab
            self.log_oov[t] = math.log(smooth / (total_emit + smooth*(m + 1)))


    def _emit_log(self, tag, word):
        '''
        Return log(P(word|tag))
        Nếu là OOV dùng log_oov
        '''

        return self.log_emit.get((tag, word), self.log_oov.get(tag, -1e18))


    def predict(self, words): #Viberti
        '''
        Viberti cho 1 câu/dòng
        words: list token của 1 câu
        return: list nhãn BIO dự đoán
        '''

        if not words or not self.trained: return []
        tags = self.tags
        neg_inf = -1e18
        n = len(words)

        V  = [{} for _ in range(n)] #Ma trận log xác suất
        BP = [{} for _ in range(n)] #backpointer
        '''
        V = [ i = 0 (token[0])       i = 1 (token[1])
            {                       {
             "B/I/O-Label": score1   "B/I/O-Label": score1   
             "B/I/O-Label": score2   "B/I/O-Label": score2
            }                       }    
        ]
        BP = [ i = 0                  i = 1                 i = 2
            {                       {                     {
             "B-Label": None        "B-Label": "O"        "B-Label": "O"
             "I-Label": None        "I-Label": "B-Label"  "I-Label": "B-Label"
             "O-Label": None        "O-Label": "O"        "O-Label": "I-Label"
            }                       }                     }
        ]

        '''
        for t in tags:
            #Log P(tag_0) + log(P(word_0|tag))
            V[0][t] = self.log_start.get(t, neg_inf) + self._emit_log(t, words[0])
            BP[0][t] = None #Chưa có tag trước đó
        #Đệ quy t = 1...n-1
        for i in range(1, n):
            w = words[i]
            for cur in tags:
                #Emission của current tag cùng từ hiện tại
                emit = self._emit_log(cur, w)
                best_score, best_prev = -math.inf, None

                #Duyệt tất cả tag trc khi tìm ra best
                for prev in tags:
                    score = (
                        V[i-1][prev] 
                        + self.log_trans.get((prev, cur), neg_inf)
                        + emit
                    )
                    if score > best_score:
                        best_score, best_prev = score, prev

                if best_prev is None: best_prev = tags[0]
                V [i][cur] = best_score
                BP[i][cur] = best_prev
        best_last, best_score = None, -math.inf
        for t in tags:
            #Cộng thêm log P(tag_last) để ưu tiên tag hay kết thúc câu
            score = V[n - 1][t] + self.log_end.get(t, neg_inf)
            if score > best_score:
                best_score, best_last = score, t
        #Fallback: khi mọi tag đều là -inf (từ hiếm) -> chọn tag đầu tiên để tránh None
        if best_last is None: best_last = tags[0]

        #Truy vết ngược
        path = [best_last]
        for i in range(n - 1, 0, -1):
            path.append(BP[i][path[-1]])
        path.reverse()

        return path

    
    def predict_task(self, task):
        '''
        Áp dụng cho toàn bộ task
        return: list (list(tag)), mỗi list là 1 dòng
        '''
        tokenized = task['tokenized']
        #Bỏ các phần tử int (đại diện cho số dòng)
        if tokenized and isinstance(tokenized[0], int):
            tokenized = tokenized[:-1]

        #Áp dụng từng dòng
        return [
            self.predict([tok[0] for tok in line])
            for line in tokenized
        ]

    def predict_tu_list_token(self, list_dong_token):
        return [
            self.predict([token[0] for token in dong])
            for dong in list_dong_token
        ]