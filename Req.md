- I want the code review agent local mode where we pass the Pull Rewquest (PR) Request , code repository.
- Agent will get the code difference from pull request and also get the checlist documents in TFS_REPO_CODE_REVIEW_CodeReviewChecklistT.
- Agent will also get the user stories linked in PR Request for review 
- Agent in case find any finding will add comments directly in PR Request to the line of code and also summary in end
- The .env provide 
  TFS_REPO_CODE_REVIEW_CodeReviewChecklistT -  Checklist Repo with all coding guidelines and checklist with *.xlsx and *.docx
  TFS_BASE_URL Base URL 
  TFS_PAT_FOR_PR Token
- I want to test the flow , so create sample PR Request in TFS_REPO_CODE_SAMPLE and sample user story and run this agent and push comment to PR Request 