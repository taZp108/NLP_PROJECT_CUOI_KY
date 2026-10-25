import pickle  # Thêm import pickle ở đầu file
import numpy as np
from scipy.special import logsumexp
from feature_extractor import FeatureExtractor


class CRF:
    """Một số ràng buộc, nếu không thì có thể phát sinh lỗi:

        1. Vị trí của các feature, các nhãn là cố định với mọi tham số hoặc ma trận và mô hình chỉ biết vị trí chứ không biết chi tiết

        1. feature mà token có bắt buộc phải nhỏ hơn số lượng feature

        2. trong một dòng tokens, số lượng features phải bằng số lượng gold_label

        3. một token không nên có 2 feature trùng nhau

        4. features và feature phải là list, không được là set
        

        Lúc train:

            +> X_train: list các dòng tokens
            +> Y_train: list các dòng bio

        Lúc pred:

            +> X_test: list các dòng token
            +> Y_test: list các dòng bio (kết quả trả ra)
    """
    def __init__(self, feature_extractor: FeatureExtractor, learning_rate=0.001):
        self.feature_extractor = feature_extractor
        self.so_nhan = len(feature_extractor.THU_TU_NHAN) + 1
        self.so_feature = len(feature_extractor.TEN_FEATURE)
        self.emission_score = np.zeros((self.so_feature, self.so_nhan))     # mỗi hàng là một feature
        self.transition_score = np.zeros((self.so_nhan, self.so_nhan))
        self.start = np.zeros(self.so_nhan)
        self.end = np.zeros(self.so_nhan)
        self.lr = learning_rate

        # 12 nhãn: "O" (id 0) và 11 loại theo THU_TU_NHAN. B-X và I-X cùng quy về id của X
        bio_thanh_id = {"O": 0}
        current_id = 1
        for nhan in feature_extractor.THU_TU_NHAN:
            bio_thanh_id[f"B-{nhan}"] = current_id
            bio_thanh_id[f"I-{nhan}"] = current_id
            current_id += 1

        id_thanh_nhan = {0: "O"}
        for id_nhan, nhan in enumerate(feature_extractor.THU_TU_NHAN, start=1):
            id_thanh_nhan[id_nhan] = nhan

        self.BIO_THANH_ID = bio_thanh_id
        self.ID_THANH_NHAN = id_thanh_nhan




    # Sẽ tính điểm của một token với tập nhãn
    def tinh_emission_score_cua_mot_token(self, feature_cua_token, nhan=None):
        if len(feature_cua_token) == 0:
            out = np.zeros(self.so_nhan)
        else:
            out = self.emission_score[feature_cua_token, :].sum(axis=0)
        return out if nhan is None else out[nhan]


    # Nhận vào tập features của các tokens, trả về điểm của tất cả các token với nhãn, dòng là token, cột là nhãn
    def tinh_emission_score_cho_nhieu_token(self, features):
        # ma trận (T, K): dòng là token, cột là nhãn
        return np.stack([self.tinh_emission_score_cua_mot_token(f) for f in features])


    # Nhận vào nhãn trước và nhãn sau để trả về score của 2 nhãn
    def tinh_transition_score(self, nhan_truoc, nhan_sau):
        return self.transition_score[nhan_truoc, nhan_sau]


    # Nhận vào tập features của các tokens và chuỗi nhãn của nó, sau đó trả về điểm 
    def tinh_sequence_score(self, features, sequence_nhan, emission_scores=None):
        E = self.tinh_emission_score_cho_nhieu_token(features) if emission_scores is None else emission_scores
        score_out = self.start[sequence_nhan[0]] + self.end[sequence_nhan[-1]]
        for i, val in enumerate(sequence_nhan):
            score_out += E[i, val]
            if i > 0:
                score_out += self.tinh_transition_score(sequence_nhan[i - 1], val)
        return score_out


    # Nhận vào ma trận điểm của các token với nhãn, trả về ma trận log(exp(score)) của các token và các nhãn, có tính emission score của vị trị xét
    def forward(self, emission_scores):
        so_token = emission_scores.shape[0]
        alpha = np.zeros((so_token, self.so_nhan))
        alpha[0] = self.start + emission_scores[0]
        for t in range(1, so_token):
            alpha[t] = emission_scores[t] + logsumexp(alpha[t - 1][:, None] + self.transition_score, axis=0)
        return alpha

    # Nhận vào ma trận điểm của các token với nhãn, trả về ma trận log(exp(score)) của các token và các nhãn, không tính emission score của vị trí đang xét
    def backward(self, emission_scores):
        so_token = emission_scores.shape[0]
        beta = np.zeros((so_token, self.so_nhan))
        beta[so_token - 1] = self.end
        for t in range(so_token - 2, -1, -1):
            beta[t] = logsumexp(self.transition_score + (emission_scores[t + 1] + beta[t + 1])[None, :], axis=1)
        return beta

    # Nhận vào ma trận forward, trả về tổng điểm của tấp cả các chuỗi log(exp(score))
    def tinh_tong_diem_chuoi(self, alpha):
        return logsumexp(alpha[-1] + self.end)               # log Z

    # Nhận vào ma trận forward, backward, tổng điểm hiện tại và trả ra ma trận xác xuất biên của các tokens và các nhãn
    def tinh_token_probability(self, alpha, beta, log_Z):
        return np.exp(alpha + beta - log_Z)               

    # Nhận vào ma trận forward, backward, ma trận emission score và tổng điểm hiện tại và trả ra ma trận có dạng là mỗi cặp vị trí sẽ có ma trận xác xuất biên chuyển giữa các nhãn
    def tinh_transition_probability(self, alpha, beta, emission_scores, log_Z):
        so_token = alpha.shape[0]
        xi = np.zeros((max(so_token - 1, 0), self.so_nhan, self.so_nhan))
        for t in range(so_token - 1):
            xi[t] = np.exp(
                alpha[t][:, None] + self.transition_score
                + (emission_scores[t + 1] + beta[t + 1])[None, :] - log_Z
            )
        return xi                                            

    # **** tính gold với expected ****
    # Nhận vào tập features của các tokens và nhãn đúng của nó để tính gold, tính theo xác suất, trả về một dict theo mỗi feature, mối feature sẽ có một list chứa tổng xác suất đối với các nhãn, tính trong cả câu
    def tinh_gold_emission(self, features, gold_labels):
        out = {}
        for feature_cua_token, nhan_dung in zip(features, gold_labels):  # Lỗi tiềm năng 1: Có thể features, gold_labels không bằng nhau
            for feature in feature_cua_token:
                if feature not in out:
                    out[feature] = np.zeros(self.so_nhan)
                out[feature][nhan_dung] += 1
        return out


    # Nhận vào tập features của các tokens và ma trận xác suất biên của từng token, có dạng dict giống gold
    def tinh_expected_emission(self, features, token_probabilities):
        out = {}
        for feature_cua_token, xac_suat_cua_token in zip(features, token_probabilities):
            for feature in feature_cua_token:
                if feature not in out:
                    out[feature] = np.zeros(self.so_nhan)
                out[feature] += xac_suat_cua_token
        return out

    # Nhận vào tập nhãn đúng và trả về gold_labels là ma trân gold của nhãn sang nhãn, và start, end là gold của start và end
    def tinh_gold_transition(self, gold_labels):
        gold_chuyen = np.zeros((self.so_nhan, self.so_nhan))
        start = np.zeros(self.so_nhan)
        end = np.zeros(self.so_nhan)
        start[gold_labels[0]] = 1
        end[gold_labels[-1]] = 1
        for a, b in zip(gold_labels[:-1], gold_labels[1:]):
            gold_chuyen[a, b] += 1
        return gold_chuyen, start, end


    # Nhận vào transition_probabilities để tính expected của chuyển nhãn và, token_probabilities để tính expected của start và end
    def tinh_expected_transition(self, transition_probabilities, token_probabilities):
        out = transition_probabilities.sum(axis=0) # đơn giản là cộng từng ma trận xác suất chuyển của tất cả các cặp vị trí 
        return out, token_probabilities[0].copy(), token_probabilities[-1].copy()



    # **** loss + gradient ****
    # Tính loss = - log(P gold)
    def tinh_loss(self, gold_score, log_Z ):
        return log_Z  - gold_score


    # Nhận vào expected và gold của emission và trả về dict gradient của từng feature đối với từng nhãn
    def tinh_gradient_emission(self, expected, gold):
        grad = {}
        for idx in set(expected) | set(gold):
            grad[idx] = expected.get(idx, 0) - gold.get(idx, 0)
        return grad

    # Nhận vào expected và gold của transition và trả về tuple
    def tinh_gradient_transition(self, expected, gold):
        return tuple(e - g for e, g in zip(expected, gold))   # (Ma trận gradient chuyển, list gradient start, list gradient end)

    # Nhận vào kết quả gradient của hai hàm trên để cập nhật trọng số cho mô hình
    def cap_nhat_trong_so(self, gradient_emission, gradient_transition):
        for feature, gradient in gradient_emission.items():
            self.emission_score[feature] -= self.lr * gradient
        gradient_chuyen, gradient_start, gradient_end = gradient_transition
        self.transition_score -= self.lr * gradient_chuyen
        self.start -= self.lr * gradient_start
        self.end -= self.lr * gradient_end

    def tinh_viterbi (self, features):
        so_token = len(features)
        if so_token == 0:
            return[]
        if so_token == 1:
            emission_scores = self.tinh_emission_score_cho_nhieu_token(features)
            best_nhan, best_val = max(((i, self.start[i] + emission_scores[0,i] + self.end[i]) for i in range(self.so_nhan)),key=lambda t: t[1])
            return [best_nhan]
        else:
            viterbi_score = np.zeros(( so_token, self.so_nhan))
            backpointer = -np.ones((so_token, self.so_nhan), dtype=int) #lưu id của nhãn hiệu quả trước đó
            emission_scores = self.tinh_emission_score_cho_nhieu_token(features)
            for i in range(self.so_nhan):
                viterbi_score[0,i] = self.start[i] + emission_scores[0,i]
            #với hàng >0, k chạy theo nhãn
            for j in range(1, so_token):
                for k in range(self.so_nhan):
                    #so sánh theo cặp phần tử để lấy được cả nhãn lẫn giá trị
                    best_nhan, best_val = max(((l, self.transition_score[l,k] + viterbi_score[j-1,l]) for l in range(self.so_nhan)),key=lambda t: t[1])
                    viterbi_score[j,k] = emission_scores[j,k] + best_val
                    if j == so_token-1:
                        viterbi_score[j,k]+= self.end[k]    
                    backpointer[j,k] = best_nhan
                    
            max_idx, max_score = max(((i,viterbi_score[so_token-1,i]) for i in range(self.so_nhan)),key=lambda t: t[1])
            final_label_list = [max_idx]
            temp= so_token-1
            while temp >= 1:
                final_label_list.append(backpointer[temp,max_idx])
                max_idx = backpointer[temp,max_idx]
                temp -=1
            final_label_list.reverse()
            return final_label_list

    # Nhận vào list nhãn loại của một dòng (vd ["O", "SKILL", "SKILL", "SALARY"]) và trả về list nhãn BIO
    # Token đầu của mỗi đoạn liên tiếp cùng nhãn là B-, các token còn lại của đoạn là I-
    def chuan_hoa_thanh_bio(self, danh_sach_nhan):
        bio = []
        nhan_truoc = "O"
        for nhan in danh_sach_nhan:
            if nhan == "O":
                bio.append("O")
            elif nhan == nhan_truoc:
                bio.append(f"I-{nhan}")
            else:
                bio.append(f"B-{nhan}")
            nhan_truoc = nhan
        return bio

    def predict(self, X_test):
        ket_qua = []

        for tokens in X_test:
            features = self.feature_extractor.trich_xuat_features(tokens)

            ids_du_doan = self.tinh_viterbi(features)

            nhan_du_doan = [
                self.ID_THANH_NHAN[int(id_nhan)]
                for id_nhan in ids_du_doan
            ]

            ket_qua.append(self.chuan_hoa_thanh_bio(nhan_du_doan))

        return ket_qua

    def train(self, X_train, Y_train, epochs):
        rng = np.random.default_rng(36) # lấy một seed random cụ thể nè hihi


        for ep in range(epochs): # Mỗi epochs sẽ chạy hết tập dữ liệu, tức là càng nhiều epochs thì mình học từ tập dữ liệu càng nhiều nè
            tong_loss = 0.0
            for i in rng.permutation(len(X_train)): # Duyệt theo từng dòng token nè

                # Lấy tập features và gold_labels cả dòng token hiện tại
                feats, gold = self.feature_extractor.trich_xuat_features(X_train[i]), list(map(lambda x: self.BIO_THANH_ID.get(x, 0) , Y_train[i]))

                if len(feats) == 0:
                    continue


                ma_tran_diem_token_va_nhan = self.tinh_emission_score_cho_nhieu_token(feats) # Lấy ma trận điểm giữa token và nhãn

                # Tính ma trận forward, backward và tổng điểm từ ma trận trên
                alpha = self.forward(ma_tran_diem_token_va_nhan) 
                beta = self.backward(ma_tran_diem_token_va_nhan)
                log_Z = self.tinh_tong_diem_chuoi(alpha)


                # Xác xuất biên của token và chuyển của các cặp token
                tok_p = self.tinh_token_probability(alpha, beta, log_Z)
                trans_p = self.tinh_transition_probability(alpha, beta, ma_tran_diem_token_va_nhan, log_Z)

                # Tính điểm của chuỗi đúng
                gold_score = self.tinh_sequence_score(feats, gold, ma_tran_diem_token_va_nhan)
                # Cập nhật loss
                tong_loss += self.tinh_loss(gold_score, log_Z)

                # Tính gold và expected cho emission và transition
                gold_em = self.tinh_gold_emission(feats, gold)
                exp_em = self.tinh_expected_emission(feats, tok_p)
                gold_tr = self.tinh_gold_transition(gold)
                exp_tr = self.tinh_expected_transition(trans_p, tok_p)

                # Cập nhật trọng số
                self.cap_nhat_trong_so(
                    self.tinh_gradient_emission(exp_em, gold_em),
                    self.tinh_gradient_transition(exp_tr, gold_tr),
                )

            # Tính tổng loss của một epochs xem nó có đang giảm hay không
            print(f"epoch {ep + 1}/{epochs}  loss TB/dòng = {tong_loss / len(X_train):.4f}")


    def luu_mo_hinh(self, duong_dan):
        """Phương thức lưu mô hình. Gọi trực tiếp trên instance: crf.luu_mo_hinh("file.npz")"""
        # Chuyển instance feature_extractor thành dạng bytes để lưu vào file npz
        fe_bytes = pickle.dumps(self.feature_extractor)
        
        np.savez(
            duong_dan,
            emission_score=self.emission_score,
            transition_score=self.transition_score,
            start=self.start,
            end=self.end,
            thu_tu_nhan=np.array(self.feature_extractor.THU_TU_NHAN),
            ten_feature=np.array(self.feature_extractor.TEN_FEATURE),
            feature_extractor_bytes=np.frombuffer(fe_bytes, dtype=np.uint8)
        )
        print(f"Đã lưu mô hình thành công vào: {duong_dan}")

    @classmethod
    def nap_mo_hinh(cls, duong_dan, feature_extractor=None, learning_rate=0.01):
        """Class method nạp mô hình. Gọi trực tiếp từ class: crf = CRF.nap_mo_hinh(...)"""
        d = np.load(duong_dan, allow_pickle=False)
        
        # 1. Ưu tiên load instance feature_extractor từ file model lên
        if "feature_extractor_bytes" in d:
            fe_bytes = d["feature_extractor_bytes"].tobytes()
            feature_extractor = pickle.loads(fe_bytes)
        
        # 2. Nếu không có trong file, kiểm tra tham số truyền vào
        if feature_extractor is None:
            raise ValueError("Không tìm thấy feature_extractor trong file và cũng không được truyền vào!")
        elif isinstance(feature_extractor, type):
            feature_extractor = feature_extractor()

        # 3. Kiểm tra tính nhất quán
        assert [str(x) for x in d["thu_tu_nhan"]] == list(feature_extractor.THU_TU_NHAN), "Thứ tự nhãn đã đổi"
        assert [str(x) for x in d["ten_feature"]] == list(feature_extractor.TEN_FEATURE), "Danh sách feature đã đổi"
        
        # 4. Khởi tạo CRF với instance chuẩn (dùng cls thay vì CRF)
        crf = cls(feature_extractor, learning_rate=learning_rate)
        crf.emission_score = d["emission_score"]
        crf.transition_score = d["transition_score"]
        crf.start = d["start"]
        crf.end = d["end"]
        
        return crf