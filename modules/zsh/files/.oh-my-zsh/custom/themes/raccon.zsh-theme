# Raccon — a quiet, two-line prompt using the terminal's desktop palette.
# Works with Oh My Zsh or when sourced directly; no Nerd Font is required.
# Optional: RACCON_PROMPT_ASCII=1, RACCON_PROMPT_GIT=0.

autoload -Uz add-zsh-hook
setopt prompt_subst

_raccon_preexec() {
  typeset -gi _raccon_started=$SECONDS
}

_raccon_git() {
  emulate -L zsh
  typeset -g _raccon_git_text=''
  [[ ${RACCON_PROMPT_GIT:-1} != 0 ]] && (( $+commands[git] )) || return 0

  local report line branch='' oid='' ahead=0 behind=0
  local staged=0 changed=0 untracked=0 conflict=0
  local -a fields
  report=$(GIT_OPTIONAL_LOCKS=0 command git status --porcelain=v2 --branch 2>/dev/null) || return 0
  for line in "${(@f)report}"; do
    case $line in
      '# branch.head '*) branch=${line#\# branch.head } ;;
      '# branch.oid '*) oid=${line#\# branch.oid } ;;
      '# branch.ab '*)
        fields=(${=line})
        ahead=${fields[3]#+}
        behind=${fields[4]#-}
        ;;
      '1 '*|'2 '*)
        [[ ${line[3]} != . ]] && staged=1
        [[ ${line[4]} != . ]] && changed=1
        ;;
      '? '*) untracked=1 ;;
      'u '*) conflict=1 ;;
    esac
  done
  [[ -n $branch ]] || return 0
  [[ $branch == '(detached)' ]] && branch="@${oid[1,7]}"

  local limit=$(( ${COLUMNS:-80} < 70 ? 12 : 24 ))
  (( ${#branch} > limit )) && branch="${branch[1,$((limit - 3))]}..."
  local flags=''
  (( staged )) && flags+='+'
  (( changed )) && flags+='*'
  (( untracked )) && flags+='?'
  (( conflict )) && flags+='!'
  [[ -n $flags ]] && flags=" $flags"
  if [[ ${RACCON_PROMPT_ASCII:-0} == 1 || $TERM == dumb ]]; then
    (( ahead > 0 )) && flags+=" >$ahead"
    (( behind > 0 )) && flags+=" <$behind"
  else
    (( ahead > 0 )) && flags+=" ↑$ahead"
    (( behind > 0 )) && flags+=" ↓$behind"
  fi
  typeset -g _raccon_git_text="git:$branch$flags"
  return 0
}

_raccon_precmd() {
  local exit_code=$?
  emulate -L zsh
  local elapsed=0 duration='' result='' label='raccon' context=''
  if (( ${+_raccon_started} )); then
    elapsed=$(( SECONDS - _raccon_started ))
    unset _raccon_started
    if (( elapsed >= 60 )); then
      duration="$((elapsed / 60))m$((elapsed % 60))s"
    elif (( elapsed >= 2 )); then
      duration="${elapsed}s"
    fi
  fi
  (( exit_code )) && result="exit $exit_code"
  [[ -n ${SSH_CONNECTION:-}${SSH_TTY:-} ]] && context="${USER:-%n}@${HOST%%.*}"
  (( EUID == 0 )) && context="root@${HOST%%.*}"
  local available_width=${COLUMNS:-80}
  (( available_width < 1 )) && available_width=80
  (( available_width < 60 )) && label=''
  _raccon_git

  # Reserve a useful path even in the narrow Raccon terminal panel.
  local path_width step
  for step in 1 2 3; do
    path_width=$(( available_width - 3
      - ${#label} - (${#label} ? 2 : 0)
      - ${#context} - (${#context} ? 1 : 0)
      - ${#_raccon_git_text} - (${#_raccon_git_text} ? 2 : 0)
      - ${#duration} - (${#duration} ? 2 : 0)
      - ${#result} - (${#result} ? 2 : 0) ))
    (( path_width >= 12 )) && break
    case $step in
      1) duration=''; context='' ;;
      2) _raccon_git_text='' ;;
    esac
  done
  (( path_width < 4 )) && path_width=4

  local top='╭─' bottom='╰─' arrow='❯'
  if [[ ${RACCON_PROMPT_ASCII:-0} == 1 || $TERM == dumb ]]; then
    top='+-'
    bottom='+-'
    arrow='>'
  fi
  (( EUID == 0 )) && arrow='#'
  local prompt="%F{8}${top}%f "
  [[ -n $label ]] && prompt+="%B%F{4}${label}%f%b  "
  # Variables are expanded once through PROMPT; escape % to prevent prompt
  # directives in branch/host names. Dollar signs are never evaluated again.
  [[ -n $context ]] && prompt+="%F{3}${context//\%/%%}%f "
  prompt+="%B%F{7}%${path_width}<...<%~%<<%f%b"
  [[ -n $_raccon_git_text ]] && prompt+="  %F{5}${_raccon_git_text//\%/%%}%f"
  [[ -n $result ]] && prompt+="  %B%F{1}${result}%f%b"
  [[ -n $duration ]] && prompt+="  %F{6}${duration}%f"
  prompt+=$'\n'"%F{8}${bottom}%f "
  if (( exit_code )); then
    prompt+="%B%F{1}${arrow}%f%b "
  else
    prompt+="%B%F{4}${arrow}%f%b "
  fi
  typeset -g _raccon_prompt=$prompt
  return 0
}

# add-zsh-hook deduplicates functions when the theme is sourced again.
add-zsh-hook preexec _raccon_preexec
add-zsh-hook precmd _raccon_precmd
PROMPT='${_raccon_prompt}'
RPROMPT=''
