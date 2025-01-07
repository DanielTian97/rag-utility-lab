from llama_cpp import Llama
from compose_prompts import *
from llama_tools import llama_tools
from experiment_tools import *
from prompt1_tools import *
import json
import sys
import concurrent.futures

if __name__=="__main__":
      if(len(sys.argv) < 8):
            print("This experiment takes 8 parameters: ")
            print("1.batch size\n2.batch step\n3.num of calls\n4.top of starts\n5.tail of starts\n6.temperature\n7.19/20\n8.retriever name (if not specified it will be bm25)")
            print("e.g. 1 1 1 10 0 0.3 19 reverse_oracle")

      batch_size = int(sys.argv[1])
      batch_step = int(sys.argv[2])
      num_calls = int(sys.argv[3])
      # start control parameters
      top_starts = int(sys.argv[4])
      tail_starts = int(sys.argv[5])
      temperature = float(sys.argv[6])
      dataset_name = str(sys.argv[7])
      
      retriever_name = 'bm25'
      if(len(sys.argv) == 9):
            retriever_name = str(sys.argv[8])
      
      # load the llm
      llm = llama_tools.load_llama()
      # load needed data
      doc_dict, queries, res = prepare_data(dataset_name, retriever_name)
      query_dict = dict(zip(range(queries.shape[0]), queries.qid.values))
      
      setting_file_name = f'./middle_products/random_answers_{batch_size}shot_{num_calls}calls_{top_starts}_{tail_starts}_{retriever_name}_dl_{dataset_name}_prompt1_settings.json'
      setting_record = {'batch_size':batch_size, 'batch_step':batch_step, 'num_calls':num_calls, \
                  'top_starts':top_starts, 'tail_starts':tail_starts, 'temperature':temperature}
      f = open(setting_file_name, "w+", encoding='UTF-8')
      json.dump(setting_record, f, indent=4)
      f.close()

      file_name = f'./middle_products/random_answers_{batch_size}shot_{num_calls}calls_{top_starts}_{tail_starts}_{retriever_name}_dl_{dataset_name}_prompt1.json'
      # result_to_write = {} #{qid:result_for_qid}

      try:
            f = open(file=file_name, mode="r")
            result_to_write = json.load(f)
            existed_qids_list = list(result_to_write.keys())
            print(existed_qids_list)
            existed_qids = len(result_to_write)
            f.close()
      except:
            f = open(file=file_name, mode="w+")
            result_to_write= {}
            existed_qids_list = []
            existed_qids = 0
            f.close()

      preamble = used_preamble()
      
      def single_generation(q_no):
                  
            print(f'q_number={q_no}--{query_dict[q_no]}')
            qid = query_dict[q_no]
            query = queries[queries.qid==qid]['query'].values[0]
                  
            varying_context_result = {} #{start: results}

            start_records, context_book = compose_context(qid=qid, res=res, batch_size=batch_size, batch_step=batch_step, top_starts=top_starts, tail_starts=tail_starts, doc_dict=doc_dict)
            for start, context in zip(start_records, context_book):
                  llm.set_seed(1000) # added 0824
                  print(f'\tstart_rank.{start}')
                  prompt = f'{preamble} \n{context}Question: "{query}"\nNow start your answer. \nAnswer: '
                  print(prompt)
                  multi_call_results = {}
                  for j in range(num_calls):
                        print(f'\t\tno.{j}')
                        result = llama_tools.single_call(llm=llm, prompt=prompt, temperature=temperature)
                        multi_call_results.update({j: result})
                  varying_context_result.update({start: multi_call_results})
                              
            result_to_write.update({qid: varying_context_result})

      q_no = existed_qids
      
      while q_no < queries.shape[0]:
            
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)

            pool.submit(single_generation(q_no))
            q_no += 1
            if(q_no < queries.shape[0]):
                  pool.submit(single_generation(q_no))
                  q_no += 1
            pool.shutdown(wait=True)

            print("A generation unit is completed.")
            update_json_result_file(file_name=file_name, result_to_write=result_to_write)