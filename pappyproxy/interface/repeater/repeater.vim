if !has('python')
    echo "Vim must support python in order to use the repeater"
    finish
endif

" Settings to make life easier
set hidden

let s:pyscript = resolve(expand('<sfile>:p:h') . '/repeater.py')

function! RepeaterAction(...)
    execute 'pyfile ' . s:pyscript
endfunc

command! -nargs=* RepeaterSetup call RepeaterAction('setup', <f-args>)
command! RepeaterSubmitBuffer call RepeaterAction('submit')

" Bind forward to <leader>f
nnoremap <leader>f :RepeaterSubmitBuffer<CR>

